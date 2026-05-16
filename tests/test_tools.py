"""Tests for src/tools.py — written first (TDD)."""

import pytest

from src.tools import TOOL_SCHEMAS, make_tool_executor


# ---------------------------------------------------------------------------
# 1. TOOL_SCHEMAS structure
# ---------------------------------------------------------------------------


def test_tool_schemas_has_exactly_two_entries():
    assert len(TOOL_SCHEMAS) == 2


def test_tool_schemas_names():
    names = [s["name"] for s in TOOL_SCHEMAS]
    assert "web_search" in names
    assert "fetch_url" in names


def test_each_schema_has_required_keys():
    for schema in TOOL_SCHEMAS:
        assert "name" in schema
        assert "description" in schema
        assert "input_schema" in schema


def test_each_schema_input_schema_is_object_type():
    for schema in TOOL_SCHEMAS:
        assert schema["input_schema"]["type"] == "object"


# ---------------------------------------------------------------------------
# 2. web_search — Brave API call
# ---------------------------------------------------------------------------


def test_web_search_calls_brave_api_correctly(mocker):
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {
        "web": {
            "results": [
                {
                    "title": "Test Title",
                    "url": "https://example.com",
                    "description": "A test snippet.",
                }
            ]
        }
    }
    mock_get = mocker.patch("httpx.get", return_value=mock_response)

    execute = make_tool_executor(brave_api_key="test-key", max_results=3)
    execute("web_search", {"query": "AI safety"})

    mock_get.assert_called_once()
    call_kwargs = mock_get.call_args

    # URL
    assert call_kwargs[0][0] == "https://api.search.brave.com/res/v1/web/search"

    # Headers
    headers = call_kwargs[1]["headers"]
    assert headers["X-Subscription-Token"] == "test-key"
    assert headers["Accept"] == "application/json"

    # Query params
    params = call_kwargs[1]["params"]
    assert params["q"] == "AI safety"
    assert params["count"] == 3

    # HTTP error surfacing
    mock_response.raise_for_status.assert_called_once()


def test_web_search_passes_timeout_to_httpx(mocker):
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {"web": {"results": []}}
    mock_get = mocker.patch("httpx.get", return_value=mock_response)

    execute = make_tool_executor(brave_api_key="test-key", max_results=3)
    execute("web_search", {"query": "test query"})

    call_kwargs = mock_get.call_args
    assert call_kwargs[1]["timeout"] == 10


def test_web_search_raises_on_http_error(mocker):
    mock_response = mocker.MagicMock()
    mock_response.raise_for_status.side_effect = Exception("401 Unauthorized")
    mocker.patch("httpx.get", return_value=mock_response)

    execute = make_tool_executor(brave_api_key="bad-key", max_results=5)
    with pytest.raises(Exception, match="401 Unauthorized"):
        execute("web_search", {"query": "test"})


def test_web_search_formats_results_as_numbered_list(mocker):
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {
        "web": {
            "results": [
                {
                    "title": "First Result",
                    "url": "https://first.com",
                    "description": "First desc.",
                },
                {
                    "title": "Second Result",
                    "url": "https://second.com",
                    "description": "Second desc.",
                },
            ]
        }
    }
    mocker.patch("httpx.get", return_value=mock_response)

    execute = make_tool_executor(brave_api_key="test-key", max_results=5)
    result = execute("web_search", {"query": "test"})

    assert "1. **First Result**" in result
    assert "URL: https://first.com" in result
    assert "Description: First desc." in result
    assert "2. **Second Result**" in result
    assert "URL: https://second.com" in result
    assert "Description: Second desc." in result


def test_web_search_returns_no_results_message_when_empty(mocker):
    mock_response = mocker.MagicMock()
    mock_response.json.return_value = {"web": {"results": []}}
    mocker.patch("httpx.get", return_value=mock_response)

    execute = make_tool_executor(brave_api_key="test-key", max_results=5)
    result = execute("web_search", {"query": "something obscure"})

    assert result == "No results found."


# ---------------------------------------------------------------------------
# 3. fetch_url
# ---------------------------------------------------------------------------


def test_fetch_url_calls_httpx_correctly(mocker):
    mock_response = mocker.MagicMock()
    mock_response.text = "x" * 100
    mock_get = mocker.patch("httpx.get", return_value=mock_response)

    execute = make_tool_executor(brave_api_key="test-key", max_results=5)
    execute("fetch_url", {"url": "https://example.com/page"})

    mock_get.assert_called_once_with(
        "https://example.com/page",
        timeout=15,
        follow_redirects=True,
    )
    mock_response.raise_for_status.assert_called_once()


def test_fetch_url_returns_first_8000_chars(mocker):
    long_text = "a" * 10_000
    mock_response = mocker.MagicMock()
    mock_response.text = long_text
    mocker.patch("httpx.get", return_value=mock_response)

    execute = make_tool_executor(brave_api_key="test-key", max_results=5)
    result = execute("fetch_url", {"url": "https://example.com"})

    assert result == long_text[:8000]
    assert len(result) == 8000


# ---------------------------------------------------------------------------
# 4. Unknown tool raises ValueError
# ---------------------------------------------------------------------------


def test_unknown_tool_raises_value_error():
    execute = make_tool_executor(brave_api_key="test-key", max_results=5)
    with pytest.raises(ValueError, match="Unknown tool"):
        execute("nonexistent_tool", {})
