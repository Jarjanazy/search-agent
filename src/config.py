"""Configuration module.

This is the ONLY module that reads os.environ. All other modules receive
configuration via dependency injection (a Config instance).
"""

import os
from dataclasses import dataclass
from datetime import date
from pathlib import Path

_REQUIRED_VARS = (
    "ANTHROPIC_API_KEY",
    "BRAVE_API_KEY",
    "GITHUB_TOKEN",
    "GITHUB_REPO",
    "GITHUB_OUTPUT_PATH",
)


@dataclass
class Config:
    anthropic_api_key: str
    brave_api_key: str
    github_token: str
    github_repo: str
    github_output_path: str
    github_branch: str
    research_topic: str
    claude_model: str
    max_search_results: int
    search_languages: list[tuple[str, float]]
    search_angles: list[str]
    search_start_date: date | None
    search_end_date: date | None


def _parse_search_languages(raw: str) -> list[tuple[str, float]]:
    """Parse SEARCH_LANGUAGES env var into normalized (lang_code, weight) pairs.

    Format: "en:0.6,ar:0.3,de:0.1"
    Weights need not sum to 1 — they are normalized automatically.
    Duplicate codes have their weights summed before normalizing.
    Empty string falls back to [("en", 1.0)].
    """
    raw = raw.strip()
    if not raw:
        return [("en", 1.0)]

    merged: dict[str, float] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split(":")
        if len(parts) != 2:
            raise ValueError(
                f"SEARCH_LANGUAGES entry {entry!r} must be 'lang_code:weight' (e.g. 'en:0.6')"
            )
        code, weight_str = parts[0].strip().lower(), parts[1].strip()
        try:
            weight = float(weight_str)
        except ValueError:
            raise ValueError(
                f"SEARCH_LANGUAGES weight {weight_str!r} for {code!r} is not a valid number"
            )
        merged[code] = merged.get(code, 0.0) + weight

    total = sum(merged.values())
    if total <= 0:
        raise ValueError("SEARCH_LANGUAGES weights must not all be zero")

    return [(code, w / total) for code, w in merged.items()]


def _load_search_angles() -> list[str]:
    """Load search angles from file path in SEARCH_ANGLES_FILE env var."""
    angles_file = os.environ.get("SEARCH_ANGLES_FILE", "").strip()
    if not angles_file:
        raise ValueError("Required environment variable 'SEARCH_ANGLES_FILE' is missing or empty.")

    path = Path(angles_file)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent / path
    if not path.exists():
        raise ValueError(f"SEARCH_ANGLES_FILE path does not exist: {angles_file!r}")

    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines()]
    angles = [line for line in lines if line]
    if not angles:
        raise ValueError(f"SEARCH_ANGLES_FILE is empty: {angles_file!r}")

    return angles


def _load_research_topic() -> str:
    """Load research topic from file path in RESEARCH_TOPIC_FILE env var."""
    topic_file = os.environ.get("RESEARCH_TOPIC_FILE", "").strip()
    if not topic_file:
        raise ValueError("Required environment variable 'RESEARCH_TOPIC_FILE' is missing or empty.")

    path = Path(topic_file)
    if not path.is_absolute():
        path = Path(__file__).resolve().parent.parent / path
    if not path.exists():
        raise ValueError(f"RESEARCH_TOPIC_FILE path does not exist: {topic_file!r}")

    content = path.read_text(encoding="utf-8").strip()
    if not content:
        raise ValueError(f"RESEARCH_TOPIC_FILE is empty: {topic_file!r}")

    return content


def load_config() -> Config:
    """Read configuration from environment variables.

    Required vars: ANTHROPIC_API_KEY, BRAVE_API_KEY, GITHUB_TOKEN,
                   GITHUB_REPO, GITHUB_OUTPUT_PATH.

    Topic: set RESEARCH_TOPIC_FILE (path to .txt file).

    Optional vars (with defaults):
        GITHUB_BRANCH         -> "main"
        CLAUDE_MODEL          -> "claude-sonnet-4-6"
        MAX_SEARCH_RESULTS    -> 5

    Raises:
        ValueError: if a required variable is missing or empty, with the
                    variable name included in the message.
    """
    for var in _REQUIRED_VARS:
        value = os.environ.get(var, "")
        if not value.strip():
            raise ValueError(
                f"Required environment variable {var!r} is missing or empty."
            )

    raw_start = os.environ.get("SEARCH_START_DATE", "").strip()
    raw_end = os.environ.get("SEARCH_END_DATE", "").strip()

    if bool(raw_start) != bool(raw_end):
        raise ValueError("SEARCH_START_DATE and SEARCH_END_DATE must both be set or both be absent.")

    search_start_date = date.fromisoformat(raw_start) if raw_start else None
    search_end_date = date.fromisoformat(raw_end) if raw_end else None

    if search_start_date and search_end_date and search_end_date < search_start_date:
        raise ValueError("SEARCH_END_DATE must not be before SEARCH_START_DATE.")

    return Config(
        anthropic_api_key=os.environ["ANTHROPIC_API_KEY"],
        brave_api_key=os.environ["BRAVE_API_KEY"],
        github_token=os.environ["GITHUB_TOKEN"],
        github_repo=os.environ["GITHUB_REPO"],
        github_output_path=os.environ["GITHUB_OUTPUT_PATH"],
        github_branch=os.environ.get("GITHUB_BRANCH", "main"),
        research_topic=_load_research_topic(),
        claude_model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6"),
        max_search_results=int(os.environ.get("MAX_SEARCH_RESULTS", "5")),
        search_languages=_parse_search_languages(os.environ.get("SEARCH_LANGUAGES", "en:1.0")),
        search_angles=_load_search_angles(),
        search_start_date=search_start_date,
        search_end_date=search_end_date,
    )
