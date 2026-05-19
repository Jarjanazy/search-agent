"""Tests for src/agent.py — plan(), research(), synthesize()."""

from __future__ import annotations

import pytest

from src.agent import plan, research, synthesize, MAX_RESEARCH_ITERATIONS, MAX_TOKENS


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
# plan() tests
# ---------------------------------------------------------------------------


def test_plan_returns_text(mocker):
    text_block = _make_text_block("## Search Strategy\n### Priority Queries\n1. query")
    response = _make_response("end_turn", [text_block])

    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = response
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    result = plan(
        api_key="test-key",
        model="claude-opus-4-7",
        topic="AI safety",
        angles=["AI safety 2026", "AI regulation"],
    )

    assert result == "## Search Strategy\n### Priority Queries\n1. query"
    # No tools passed to planning call
    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert "tools" not in call_kwargs


def test_plan_uses_planning_max_tokens(mocker):
    text_block = _make_text_block("plan")
    response = _make_response("end_turn", [text_block])

    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = response
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    plan(api_key="test-key", model="claude-opus-4-7", topic="topic", angles=["a"])

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert call_kwargs["max_tokens"] == 1024


def test_plan_includes_angles_in_user_message(mocker):
    text_block = _make_text_block("plan")
    response = _make_response("end_turn", [text_block])

    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = response
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    plan(
        api_key="test-key",
        model="claude-opus-4-7",
        topic="oil prices",
        angles=["OPEC cuts", "demand forecast"],
    )

    messages = mock_client.messages.create.call_args.kwargs["messages"]
    user_content = messages[0]["content"]
    assert "OPEC cuts" in user_content
    assert "demand forecast" in user_content


def test_plan_returns_empty_string_when_no_text_block(mocker):
    response = _make_response("end_turn", [])

    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = response
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    result = plan(api_key="test-key", model="claude-opus-4-7", topic="topic", angles=["a"])
    assert result == ""


# ---------------------------------------------------------------------------
# research() tests
# ---------------------------------------------------------------------------


def test_research_returns_messages_on_end_turn(mocker):
    text_block = _make_text_block("Research complete.")
    response = _make_response("end_turn", [text_block])

    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = response
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    tool_executor = mocker.MagicMock()
    messages = research(
        api_key="test-key",
        model="claude-sonnet-4-6",
        topic="AI safety",
        angles=["AI safety 2026"],
        plan_text="## Search Strategy\n1. query",
        tool_executor=tool_executor,
        tool_schemas=[],
    )

    assert isinstance(messages, list)
    assert messages[0]["role"] == "user"
    tool_executor.assert_not_called()


def test_research_injects_plan_as_first_user_message(mocker):
    text_block = _make_text_block("Research complete.")
    response = _make_response("end_turn", [text_block])

    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = response
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    research(
        api_key="test-key",
        model="claude-sonnet-4-6",
        topic="oil prices",
        angles=["OPEC cuts"],
        plan_text="## My Plan\n1. search OPEC",
        tool_executor=mocker.MagicMock(),
        tool_schemas=[],
    )

    messages = mock_client.messages.create.call_args.kwargs["messages"]
    first_content = messages[0]["content"]
    assert "## My Plan" in first_content
    assert "oil prices" in first_content


def test_research_calls_tool_then_returns_messages(mocker):
    tool_block = _make_tool_use_block("tool-1", "web_search", {"query": "AI safety"})
    tool_response = _make_response("tool_use", [tool_block])

    text_block = _make_text_block("Research complete.")
    final_response = _make_response("end_turn", [text_block])

    mock_client = mocker.MagicMock()
    mock_client.messages.create.side_effect = [tool_response, final_response]
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    tool_executor = mocker.MagicMock(return_value="Search results here")

    messages = research(
        api_key="test-key",
        model="claude-sonnet-4-6",
        topic="AI safety",
        angles=["AI safety 2026"],
        plan_text="plan",
        tool_executor=tool_executor,
        tool_schemas=[],
    )

    tool_executor.assert_called_once_with("web_search", {"query": "AI safety"})
    # messages: [user, assistant, user-with-tool-result, assistant]
    assert len(messages) == 4
    tool_result_msg = messages[2]
    assert tool_result_msg["role"] == "user"
    assert tool_result_msg["content"][0]["type"] == "tool_result"
    assert tool_result_msg["content"][0]["tool_use_id"] == "tool-1"
    assert tool_result_msg["content"][0]["content"] == "Search results here"


def test_research_multiple_tool_calls_in_one_response(mocker):
    tool_block_a = _make_tool_use_block("t-1", "web_search", {"query": "query A"})
    tool_block_b = _make_tool_use_block("t-2", "fetch_url", {"url": "https://example.com"})
    tool_response = _make_response("tool_use", [tool_block_a, tool_block_b])

    text_block = _make_text_block("Research complete.")
    final_response = _make_response("end_turn", [text_block])

    mock_client = mocker.MagicMock()
    mock_client.messages.create.side_effect = [tool_response, final_response]
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    tool_executor = mocker.MagicMock(side_effect=["Result A", "Result B"])

    research(
        api_key="test-key",
        model="claude-sonnet-4-6",
        topic="topic",
        angles=["q1"],
        plan_text="plan",
        tool_executor=tool_executor,
        tool_schemas=[],
    )

    assert tool_executor.call_count == 2
    second_call_messages = mock_client.messages.create.call_args_list[1][1]["messages"]
    tool_result_msg = second_call_messages[-1]
    assert len(tool_result_msg["content"]) == 2
    assert tool_result_msg["content"][0]["tool_use_id"] == "t-1"
    assert tool_result_msg["content"][0]["content"] == "Result A"
    assert tool_result_msg["content"][1]["tool_use_id"] == "t-2"
    assert tool_result_msg["content"][1]["content"] == "Result B"


def test_research_raises_after_max_iterations(mocker):
    tool_block = _make_tool_use_block("t-loop", "web_search", {"query": "forever"})
    tool_response = _make_response("tool_use", [tool_block])

    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = tool_response
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    with pytest.raises(RuntimeError, match=f"Max iterations \\({MAX_RESEARCH_ITERATIONS}\\) reached without end_turn"):
        research(
            api_key="test-key",
            model="claude-sonnet-4-6",
            topic="topic",
            angles=["q1"],
            plan_text="plan",
            tool_executor=mocker.MagicMock(return_value="result"),
            tool_schemas=[],
        )

    assert mock_client.messages.create.call_count == MAX_RESEARCH_ITERATIONS


def test_research_raises_on_unexpected_stop_reason(mocker):
    response = _make_response("stop_sequence", [])

    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = response
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    with pytest.raises(ValueError, match="Unexpected stop_reason: 'stop_sequence'"):
        research(
            api_key="test-key",
            model="claude-sonnet-4-6",
            topic="topic",
            angles=["q1"],
            plan_text="plan",
            tool_executor=mocker.MagicMock(),
            tool_schemas=[],
        )


def test_research_tool_executor_exception_returned_as_error_result(mocker):
    tool_block = _make_tool_use_block("t-err", "web_search", {"query": "kaboom"})
    tool_response = _make_response("tool_use", [tool_block])

    text_block = _make_text_block("Research complete.")
    final_response = _make_response("end_turn", [text_block])

    mock_client = mocker.MagicMock()
    mock_client.messages.create.side_effect = [tool_response, final_response]
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    research(
        api_key="test-key",
        model="claude-sonnet-4-6",
        topic="topic",
        angles=["q1"],
        plan_text="plan",
        tool_executor=mocker.MagicMock(side_effect=RuntimeError("network timeout")),
        tool_schemas=[],
    )

    second_call_messages = mock_client.messages.create.call_args_list[1][1]["messages"]
    tool_result_msg = second_call_messages[-1]
    content = tool_result_msg["content"][0]
    assert content["type"] == "tool_result"
    assert "Error executing tool web_search" in content["content"]
    assert "network timeout" in content["content"]


def test_research_tool_use_with_no_blocks_raises(mocker):
    text_block = _make_text_block("some text")
    response = _make_response("tool_use", [text_block])

    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = response
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    with pytest.raises(ValueError, match="stop_reason='tool_use' but no tool_use blocks in response"):
        research(
            api_key="test-key",
            model="claude-sonnet-4-6",
            topic="topic",
            angles=["q1"],
            plan_text="plan",
            tool_executor=mocker.MagicMock(),
            tool_schemas=[],
        )


def test_research_returns_messages_on_max_tokens(mocker):
    text_block = _make_text_block("Partial.")
    response = _make_response("max_tokens", [text_block])

    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = response
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    messages = research(
        api_key="test-key",
        model="claude-sonnet-4-6",
        topic="topic",
        angles=["q1"],
        plan_text="plan",
        tool_executor=mocker.MagicMock(),
        tool_schemas=[],
    )

    assert isinstance(messages, list)


# ---------------------------------------------------------------------------
# synthesize() tests
# ---------------------------------------------------------------------------


def test_synthesize_returns_report(mocker):
    text_block = _make_text_block("# Report\n\nContent here.")
    response = _make_response("end_turn", [text_block])

    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = response
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    fake_messages = [{"role": "user", "content": "Research this topic: AI safety\n\nFollow this search plan:\nplan"}]
    result = synthesize(api_key="test-key", model="claude-opus-4-7", messages=fake_messages)

    assert result == "# Report\n\nContent here."


def test_synthesize_appends_write_report_instruction(mocker):
    text_block = _make_text_block("# Report")
    response = _make_response("end_turn", [text_block])

    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = response
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    fake_messages = [{"role": "user", "content": "research data"}]
    synthesize(api_key="test-key", model="claude-opus-4-7", messages=fake_messages)

    call_messages = mock_client.messages.create.call_args.kwargs["messages"]
    last_msg = call_messages[-1]
    assert last_msg["role"] == "user"
    assert "Write the final report now" in last_msg["content"]


def test_synthesize_does_not_pass_tools(mocker):
    text_block = _make_text_block("# Report")
    response = _make_response("end_turn", [text_block])

    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = response
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    synthesize(api_key="test-key", model="claude-opus-4-7", messages=[])

    call_kwargs = mock_client.messages.create.call_args.kwargs
    assert "tools" not in call_kwargs


def test_synthesize_returns_empty_string_when_no_text_block(mocker):
    response = _make_response("end_turn", [])

    mock_client = mocker.MagicMock()
    mock_client.messages.create.return_value = response
    mocker.patch("anthropic.Anthropic", return_value=mock_client)

    result = synthesize(api_key="test-key", model="claude-opus-4-7", messages=[])
    assert result == ""


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


def test_max_tokens_constant():
    assert MAX_TOKENS == 4096


def test_max_research_iterations_constant():
    assert MAX_RESEARCH_ITERATIONS == 20
