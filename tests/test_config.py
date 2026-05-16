"""Tests for src/config.py — written first (TDD)."""

import pytest

from src.config import Config, load_config

# Minimal set of required env vars for a valid config
REQUIRED_VARS = {
    "ANTHROPIC_API_KEY": "test-anthropic-key",
    "BRAVE_API_KEY": "test-brave-key",
    "GITHUB_TOKEN": "test-github-token",
    "GITHUB_REPO": "user/repo",
    "GITHUB_OUTPUT_PATH": "output/research.md",
    "RESEARCH_TOPIC": "AI safety",
}


def set_required(monkeypatch):
    """Helper: set all required env vars via monkeypatch."""
    for key, value in REQUIRED_VARS.items():
        monkeypatch.setenv(key, value)


# ---------------------------------------------------------------------------
# 1. load_config() returns correct Config when all required vars are set
# ---------------------------------------------------------------------------


def test_load_config_returns_config_dataclass(monkeypatch):
    set_required(monkeypatch)
    cfg = load_config()
    assert isinstance(cfg, Config)


def test_load_config_required_fields(monkeypatch):
    set_required(monkeypatch)
    cfg = load_config()
    assert cfg.anthropic_api_key == "test-anthropic-key"
    assert cfg.brave_api_key == "test-brave-key"
    assert cfg.github_token == "test-github-token"
    assert cfg.github_repo == "user/repo"
    assert cfg.github_output_path == "output/research.md"
    assert cfg.research_topic == "AI safety"


# ---------------------------------------------------------------------------
# 2. Optional vars use correct defaults when not set
# ---------------------------------------------------------------------------


def test_default_github_branch(monkeypatch):
    set_required(monkeypatch)
    monkeypatch.delenv("GITHUB_BRANCH", raising=False)
    cfg = load_config()
    assert cfg.github_branch == "main"


def test_default_claude_model(monkeypatch):
    set_required(monkeypatch)
    monkeypatch.delenv("CLAUDE_MODEL", raising=False)
    cfg = load_config()
    assert cfg.claude_model == "claude-sonnet-4-6"


def test_default_max_search_results(monkeypatch):
    set_required(monkeypatch)
    monkeypatch.delenv("MAX_SEARCH_RESULTS", raising=False)
    cfg = load_config()
    assert cfg.max_search_results == 5


# ---------------------------------------------------------------------------
# 3. Optional vars respect overrides when set
# ---------------------------------------------------------------------------


def test_override_github_branch(monkeypatch):
    set_required(monkeypatch)
    monkeypatch.setenv("GITHUB_BRANCH", "feature/my-branch")
    cfg = load_config()
    assert cfg.github_branch == "feature/my-branch"


def test_override_claude_model(monkeypatch):
    set_required(monkeypatch)
    monkeypatch.setenv("CLAUDE_MODEL", "claude-opus-4-5")
    cfg = load_config()
    assert cfg.claude_model == "claude-opus-4-5"


def test_override_max_search_results(monkeypatch):
    set_required(monkeypatch)
    monkeypatch.setenv("MAX_SEARCH_RESULTS", "10")
    cfg = load_config()
    assert cfg.max_search_results == 10


def test_max_search_results_is_int(monkeypatch):
    set_required(monkeypatch)
    monkeypatch.setenv("MAX_SEARCH_RESULTS", "7")
    cfg = load_config()
    assert isinstance(cfg.max_search_results, int)


# ---------------------------------------------------------------------------
# 4. Missing each required var individually raises ValueError with var name
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("missing_var", list(REQUIRED_VARS.keys()))
def test_missing_required_var_raises_value_error(monkeypatch, missing_var):
    set_required(monkeypatch)
    monkeypatch.delenv(missing_var)
    with pytest.raises(ValueError, match=missing_var):
        load_config()


@pytest.mark.parametrize("empty_var", list(REQUIRED_VARS.keys()))
def test_empty_required_var_raises_value_error(monkeypatch, empty_var):
    set_required(monkeypatch)
    monkeypatch.setenv(empty_var, "")
    with pytest.raises(ValueError, match=empty_var):
        load_config()


def test_whitespace_only_required_var_raises(monkeypatch):
    # set all required vars
    monkeypatch.setenv("ANTHROPIC_API_KEY", "   ")
    monkeypatch.setenv("BRAVE_API_KEY", "key")
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setenv("GITHUB_REPO", "owner/repo")
    monkeypatch.setenv("GITHUB_OUTPUT_PATH", "research/latest.md")
    monkeypatch.setenv("RESEARCH_TOPIC", "AI safety")
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        load_config()
