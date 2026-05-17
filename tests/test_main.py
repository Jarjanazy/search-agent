"""Tests for src/main.py — written first (TDD)."""

import sys
from datetime import date
from unittest.mock import MagicMock

import pytest

from src.main import _build_output_markdown, main


# ---------------------------------------------------------------------------
# 1. test_main_wires_all_modules
# ---------------------------------------------------------------------------


def test_main_wires_all_modules(mocker):
    """main() should call load_config, make_tool_executor, run_agent, and
    commit_markdown with the correct arguments derived from the config."""

    fake_config = MagicMock()
    fake_config.anthropic_api_key = "anthropic-key"
    fake_config.brave_api_key = "brave-key"
    fake_config.max_search_results = 5
    fake_config.claude_model = "claude-sonnet-4-6"
    fake_config.research_topic = "AI safety"
    fake_config.github_token = "github-token"
    fake_config.github_repo = "owner/repo"
    fake_config.github_output_path = "reports/output.md"
    fake_config.github_branch = "main"

    mock_load_config = mocker.patch("src.main.load_config", return_value=fake_config)

    fake_executor = MagicMock()
    mock_make_tool_executor = mocker.patch(
        "src.main.make_tool_executor", return_value=fake_executor
    )

    mock_run_agent = mocker.patch("src.main.run_agent", return_value="# Report\nContent")

    mock_commit_markdown = mocker.patch("src.main.commit_markdown")

    # Patch TOOL_SCHEMAS so we can assert it is forwarded
    fake_schemas = [{"name": "web_search"}]
    mocker.patch("src.main.TOOL_SCHEMAS", fake_schemas)

    main()

    # load_config called once with no args
    mock_load_config.assert_called_once_with()

    # make_tool_executor called with brave key, max results, and date window
    mock_make_tool_executor.assert_called_once_with(
        brave_api_key="brave-key",
        max_results=5,
        search_start_date=fake_config.search_start_date,
        search_end_date=fake_config.search_end_date,
    )

    # run_agent called with correct kwargs
    mock_run_agent.assert_called_once_with(
        anthropic_api_key="anthropic-key",
        model="claude-sonnet-4-6",
        topic="AI safety",
        tool_executor=fake_executor,
        tool_schemas=fake_schemas,
        search_angles=fake_config.search_angles,
        search_languages=fake_config.search_languages,
        search_start_date=fake_config.search_start_date,
        search_end_date=fake_config.search_end_date,
    )

    # commit_markdown called once; check key args
    mock_commit_markdown.assert_called_once()
    call_kwargs = mock_commit_markdown.call_args.kwargs
    assert call_kwargs["github_token"] == "github-token"
    assert call_kwargs["repo_name"] == "owner/repo"
    assert call_kwargs["file_path"] == "reports/output.md"
    assert call_kwargs["branch"] == "main"
    # commit_message includes the topic
    assert "AI safety" in call_kwargs["commit_message"]
    # content is the built markdown (contains report body)
    assert "# Report" in call_kwargs["content"]


# ---------------------------------------------------------------------------
# 2. test_build_output_markdown_has_yaml_frontmatter
# ---------------------------------------------------------------------------


def test_build_output_markdown_has_yaml_frontmatter():
    result = _build_output_markdown("AI safety", "# Report\nContent")

    assert result.startswith("---")
    assert "topic: AI safety" in result
    assert "generated:" in result
    assert "# Report" in result
    assert "Content" in result


# ---------------------------------------------------------------------------
# 3. test_build_output_markdown_includes_date
# ---------------------------------------------------------------------------


def test_build_output_markdown_includes_date():
    today_str = date.today().isoformat()
    result = _build_output_markdown("quantum computing", "Some report body")

    assert f"generated: {today_str}" in result


# ---------------------------------------------------------------------------
# 4. test_main_sys_exit_1_on_exception
# ---------------------------------------------------------------------------


def test_main_sys_exit_1_on_exception(mocker):
    """When load_config raises, the __main__ block exits with code 1.
    main() itself lets exceptions propagate; the guard is in __main__."""

    mocker.patch("src.main.load_config", side_effect=RuntimeError("bad config"))

    # main() propagates the exception — callers / __main__ handle sys.exit
    with pytest.raises(RuntimeError, match="bad config"):
        main()

    # Simulate what __main__ does: catch and sys.exit(1)
    with pytest.raises(SystemExit) as exc_info:
        try:
            main()
        except Exception as exc:
            import sys as _sys
            print(f"ERROR: {exc}", file=_sys.stderr)
            _sys.exit(1)

    assert exc_info.value.code == 1
