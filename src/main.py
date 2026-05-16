import sys
from datetime import date
from pathlib import Path

from src.config import load_config
from src.tools import TOOL_SCHEMAS, make_tool_executor
from src.agent import run_agent
from src.github_client import commit_markdown

FALLBACK_PATH = Path("data/fallback_report.md")


def _build_output_markdown(topic: str, report: str) -> str:
    today = date.today().isoformat()
    short_topic = topic.splitlines()[0].split("—")[0].strip()
    return f"""---
topic: {short_topic}
generated: {today}
---

{report}
"""


def _do_commit(config, content: str) -> None:
    commit_markdown(
        github_token=config.github_token,
        repo_name=config.github_repo,
        file_path=config.github_output_path,
        content=content,
        branch=config.github_branch,
        commit_message=f"research: update {config.research_topic} report ({date.today().isoformat()})",
    )


def main() -> None:
    print("Loading config...")
    config = load_config()

    if FALLBACK_PATH.exists():
        print(f"Found fallback report at {FALLBACK_PATH}. Retrying commit...")
        try:
            _do_commit(config, FALLBACK_PATH.read_text(encoding="utf-8"))
            FALLBACK_PATH.unlink()
            print("Fallback committed and removed. Proceeding with new run...")
        except Exception as exc:
            print(f"Fallback commit still failing: {exc}. Fix GitHub token first.", file=sys.stderr)
            sys.exit(1)

    print(f"Starting research on: {config.research_topic}")
    tool_executor = make_tool_executor(
        brave_api_key=config.brave_api_key,
        max_results=config.max_search_results,
    )

    print("Running agent...")
    report = run_agent(
        anthropic_api_key=config.anthropic_api_key,
        model=config.claude_model,
        topic=config.research_topic,
        tool_executor=tool_executor,
        tool_schemas=TOOL_SCHEMAS,
        search_angles=config.search_angles,
        search_languages=config.search_languages,
    )

    print("Building output markdown...")
    output_md = _build_output_markdown(topic=config.research_topic, report=report)

    print(f"Committing to {config.github_repo}/{config.github_output_path}...")
    try:
        _do_commit(config, output_md)
    except Exception as exc:
        FALLBACK_PATH.write_text(output_md, encoding="utf-8")
        print(f"Commit failed: {exc}\nReport saved to {FALLBACK_PATH}.", file=sys.stderr)
        sys.exit(1)

    print("Done.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
