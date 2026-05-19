"""Orchestrates the three-phase research pipeline."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable

from src.agent import plan, research, synthesize
from src.run_logger import RunLogger


def run_pipeline(
    anthropic_api_key: str,
    planning_model: str,
    research_model: str,
    synthesis_model: str,
    topic: str,
    search_angles: list[str],
    tool_executor: Callable[[str, dict], str],
    tool_schemas: list[dict],
    thinking_output_dir: str = "runs",
    search_languages: list[tuple[str, float]] | None = None,
    search_start_date: date | None = None,
    search_end_date: date | None = None,
) -> str:
    """Run the full three-phase pipeline and return the final report."""
    logger = RunLogger(base_dir=Path(thinking_output_dir))

    print(f"Phase 1/3: Planning ({planning_model})...")
    plan_text = plan(
        api_key=anthropic_api_key,
        model=planning_model,
        topic=topic,
        angles=search_angles,
        languages=search_languages,
        start_date=search_start_date,
        end_date=search_end_date,
    )
    logger.save(1, plan_text)

    print(f"Phase 2/3: Research ({research_model})...")
    messages = research(
        api_key=anthropic_api_key,
        model=research_model,
        topic=topic,
        angles=search_angles,
        plan_text=plan_text,
        tool_executor=tool_executor,
        tool_schemas=tool_schemas,
        languages=search_languages,
        start_date=search_start_date,
        end_date=search_end_date,
    )
    logger.save(2, messages)

    print(f"Phase 3/3: Synthesis ({synthesis_model})...")
    report = synthesize(
        api_key=anthropic_api_key,
        model=synthesis_model,
        messages=messages,
    )
    logger.save(3, report)

    return report
