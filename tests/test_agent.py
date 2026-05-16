"""Tests for src/agent.py — written first (TDD)."""

from __future__ import annotations

import pytest

from src.agent import run_agent, MAX_ITERATIONS, MAX_TOKENS


# ---------------------------------------------------------------------------
# Helpers — build mock response objects
# ---------------------------------------------------------------------------


def _make_text_block(text: str):
    block = type("TextBlock", (), {"type": "text", "text": text})()
    return block


def _make_tool_use_block(id: str, name: str, input: dict):
    block = type("ToolUseBlock", (), {"type": "tool_use", "id": id, "name": name, "input": input})()
    return block


def _make_response(stop_reason: str, content: list):
    resp = type("Response", (), {"stop_reason": stop_reason, "content": content})()
    return resp


# ---------------------------------------------------------------------------
# 1. Returns text on end_turn
# ---------------------------------------------------------------------------


def test_returns_text_on_end_turn(mocker):
    text_block = _make_text_block("# Report\n\nThis is the report.")
    response = _make_response("end_turn", [text_block])

    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = response
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    tool_executor = mocker.MagicMock()
    result = run_agent(
        anthropic_api_key="test-key",
        model="claude-3-5-sonnet-20241022",
        topic="AI safety",
        tool_executor=tool_executor,
        tool_schemas=[],
    )

    assert result == "# Report\n\nThis is the report."
    tool_executor.assert_not_called()


# ---------------------------------------------------------------------------
# 2. Calls tool and appends result on tool_use, then continues to end_turn
# ---------------------------------------------------------------------------


def test_calls_tool_on_tool_use_then_end_turn(mocker):
    tool_block = _make_tool_use_block("tool-1", "web_search", {"query": "AI safety"})
    tool_response = _make_response("tool_use", [tool_block])

    text_block = _make_text_block("# Final Report")
    final_response = _make_response("end_turn", [text_block])

    mock_client = mocker.MagicMock()
    mock_client.messages.create.side_effect = [tool_response, final_response]
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    tool_executor = mocker.MagicMock(return_value="Search results here")

    result = run_agent(
        anthropic_api_key="test-key",
        model="claude-3-5-sonnet-20241022",
        topic="AI safety",
        tool_executor=tool_executor,
        tool_schemas=[],
    )

    assert result == "# Final Report"
    tool_executor.assert_called_once_with("web_search", {"query": "AI safety"})

    # Verify second call includes the tool result
    second_call_messages = mock_client.messages.create.call_args_list[1][1]["messages"]
    # messages: [user, assistant, user-with-tool-result]
    assert len(second_call_messages) == 3
    tool_result_msg = second_call_messages[2]
    assert tool_result_msg["role"] == "user"
    assert tool_result_msg["content"][0]["type"] == "tool_result"
    assert tool_result_msg["content"][0]["tool_use_id"] == "tool-1"
    assert tool_result_msg["content"][0]["content"] == "Search results here"


# ---------------------------------------------------------------------------
# 3. Multiple tool calls in one response handled correctly
# ---------------------------------------------------------------------------


def test_multiple_tool_calls_in_one_response(mocker):
    tool_block_a = _make_tool_use_block("t-1", "web_search", {"query": "query A"})
    tool_block_b = _make_tool_use_block("t-2", "fetch_url", {"url": "https://example.com"})
    tool_response = _make_response("tool_use", [tool_block_a, tool_block_b])

    text_block = _make_text_block("# Final Report")
    final_response = _make_response("end_turn", [text_block])

    mock_client = mocker.MagicMock()
    mock_client.messages.create.side_effect = [tool_response, final_response]
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    tool_executor = mocker.MagicMock(side_effect=["Result A", "Result B"])

    result = run_agent(
        anthropic_api_key="test-key",
        model="claude-3-5-sonnet-20241022",
        topic="topic",
        tool_executor=tool_executor,
        tool_schemas=[],
    )

    assert result == "# Final Report"
    assert tool_executor.call_count == 2
    tool_executor.assert_any_call("web_search", {"query": "query A"})
    tool_executor.assert_any_call("fetch_url", {"url": "https://example.com"})

    # The tool result message should have 2 tool_result blocks
    second_call_messages = mock_client.messages.create.call_args_list[1][1]["messages"]
    tool_result_msg = second_call_messages[-1]
    assert len(tool_result_msg["content"]) == 2
    assert tool_result_msg["content"][0]["tool_use_id"] == "t-1"
    assert tool_result_msg["content"][0]["content"] == "Result A"
    assert tool_result_msg["content"][1]["tool_use_id"] == "t-2"
    assert tool_result_msg["content"][1]["content"] == "Result B"


# ---------------------------------------------------------------------------
# 4. Raises RuntimeError after MAX_ITERATIONS of tool_use
# ---------------------------------------------------------------------------


def test_raises_runtime_error_after_max_iterations(mocker):
    tool_block = _make_tool_use_block("t-loop", "web_search", {"query": "forever"})
    tool_response = _make_response("tool_use", [tool_block])

    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = tool_response
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    tool_executor = mocker.MagicMock(return_value="result")

    with pytest.raises(RuntimeError, match=f"Max iterations \\({MAX_ITERATIONS}\\) reached without end_turn"):
        run_agent(
            anthropic_api_key="test-key",
            model="claude-3-5-sonnet-20241022",
            topic="topic",
            tool_executor=tool_executor,
            tool_schemas=[],
        )

    assert mock_client.messages.create.call_count == MAX_ITERATIONS


# ---------------------------------------------------------------------------
# 5. Raises ValueError on unexpected stop_reason
# ---------------------------------------------------------------------------


def test_raises_value_error_on_unexpected_stop_reason(mocker):
    response = _make_response("stop_sequence", [])

    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = response
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    with pytest.raises(ValueError, match="Unexpected stop_reason: 'stop_sequence'"):
        run_agent(
            anthropic_api_key="test-key",
            model="claude-3-5-sonnet-20241022",
            topic="topic",
            tool_executor=mocker.MagicMock(),
            tool_schemas=[],
        )


# ---------------------------------------------------------------------------
# 5b. Returns text on max_tokens stop_reason (not an error)
# ---------------------------------------------------------------------------


def test_returns_text_on_max_tokens(mocker):
    text_block = _make_text_block("# Partial Report\n\nTruncated due to token limit.")
    response = _make_response("max_tokens", [text_block])

    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = response
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    result = run_agent(
        anthropic_api_key="test-key",
        model="claude-3-5-sonnet-20241022",
        topic="topic",
        tool_executor=mocker.MagicMock(),
        tool_schemas=[],
    )

    assert result == "# Partial Report\n\nTruncated due to token limit."


def test_returns_empty_string_on_max_tokens_with_no_text_block(mocker):
    response = _make_response("max_tokens", [])

    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = response
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    result = run_agent(
        anthropic_api_key="test-key",
        model="claude-3-5-sonnet-20241022",
        topic="topic",
        tool_executor=mocker.MagicMock(),
        tool_schemas=[],
    )

    assert result == ""


# ---------------------------------------------------------------------------
# 5c. MAX_TOKENS constant is exported and correct
# ---------------------------------------------------------------------------


def test_max_tokens_constant():
    assert MAX_TOKENS == 4096


# ---------------------------------------------------------------------------
# 6. Tool executor exception returned as error string in tool_result
# ---------------------------------------------------------------------------


def test_tool_executor_exception_returned_as_error_result(mocker):
    tool_block = _make_tool_use_block("t-err", "web_search", {"query": "kaboom"})
    tool_response = _make_response("tool_use", [tool_block])

    text_block = _make_text_block("# Report after error")
    final_response = _make_response("end_turn", [text_block])

    mock_client = mocker.MagicMock()
    mock_client.messages.create.side_effect = [tool_response, final_response]
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    tool_executor = mocker.MagicMock(side_effect=RuntimeError("network timeout"))

    result = run_agent(
        anthropic_api_key="test-key",
        model="claude-3-5-sonnet-20241022",
        topic="topic",
        tool_executor=tool_executor,
        tool_schemas=[],
    )

    # Agent should not crash; it continues to end_turn and returns the final text
    assert result == "# Report after error"

    # The tool_result sent back to Claude must contain the error string
    second_call_messages = mock_client.messages.create.call_args_list[1][1]["messages"]
    tool_result_msg = second_call_messages[-1]
    assert tool_result_msg["role"] == "user"
    assert len(tool_result_msg["content"]) == 1
    content = tool_result_msg["content"][0]
    assert content["type"] == "tool_result"
    assert content["tool_use_id"] == "t-err"
    assert "Error executing tool web_search" in content["content"]
    assert "network timeout" in content["content"]


# ---------------------------------------------------------------------------
# 7. stop_reason=tool_use with no tool_use blocks raises ValueError
# ---------------------------------------------------------------------------


def test_tool_use_with_no_blocks_raises(mocker):
    # Response claims tool_use but content has only a text block (no tool_use blocks)
    text_block = _make_text_block("some text")
    response = _make_response("tool_use", [text_block])

    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = response
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    with pytest.raises(ValueError, match="stop_reason='tool_use' but no tool_use blocks in response"):
        run_agent(
            anthropic_api_key="test-key",
            model="claude-3-5-sonnet-20241022",
            topic="topic",
            tool_executor=mocker.MagicMock(),
            tool_schemas=[],
        )
