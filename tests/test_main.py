"""Tests for src/main.py."""

import sys
from datetime import date
from unittest.mock import MagicMock

import pytest

from src.main import _build_output_markdown, main


# ---------------------------------------------------------------------------
# 1. test_main_wires_all_modules
# ---------------------------------------------------------------------------


def test_main_wires_all_modules(mocker):
    """main() calls load_config, make_tool_executor, run_pipeline, commit_markdown."""

    fake_config = MagicMock()
    fake_config.anthropic_api_key = "anthropic-key"
    fake_config.brave_api_key = "brave-key"
    fake_config.max_search_results = 5
    fake_config.planning_model = "claude-opus-4-7"
    fake_config.research_model = "claude-sonnet-4-6"
    fake_config.synthesis_model = "claude-opus-4-7"
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

    mock_run_pipeline = mocker.patch("src.main.run_pipeline", return_value="# Report\nContent")

    mock_commit_markdown = mocker.patch("src.main.commit_markdown")

    fake_schemas = [{"name": "web_search"}]
    mocker.patch("src.main.TOOL_SCHEMAS", fake_schemas)

    main()

    mock_load_config.assert_called_once_with()

    mock_make_tool_executor.assert_called_once_with(
        brave_api_key="brave-key",
        max_results=5,
        search_start_date=fake_config.search_start_date,
        search_end_date=fake_config.search_end_date,
    )

    mock_run_pipeline.assert_called_once_with(
        anthropic_api_key="anthropic-key",
        planning_model="claude-opus-4-7",
        research_model="claude-sonnet-4-6",
        synthesis_model="claude-opus-4-7",
        topic="AI safety",
        search_angles=fake_config.search_angles,
        tool_executor=fake_executor,
        tool_schemas=fake_schemas,
        thinking_output_dir=fake_config.thinking_output_dir,
        search_languages=fake_config.search_languages,
        search_start_date=fake_config.search_start_date,
        search_end_date=fake_config.search_end_date,
    )

    mock_commit_markdown.assert_called_once()
    call_kwargs = mock_commit_markdown.call_args.kwargs
    assert call_kwargs["github_token"] == "github-token"
    assert call_kwargs["repo_name"] == "owner/repo"
    assert call_kwargs["file_path"] == "reports/output.md"
    assert call_kwargs["branch"] == "main"
    assert "AI safety" in call_kwargs["commit_message"]
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
    mocker.patch("src.main.load_config", side_effect=RuntimeError("bad config"))

    with pytest.raises(RuntimeError, match="bad config"):
        main()

    with pytest.raises(SystemExit) as exc_info:
        try:
            main()
        except Exception as exc:
            import sys as _sys
            print(f"ERROR: {exc}", file=_sys.stderr)
            _sys.exit(1)

    assert exc_info.value.code == 1
