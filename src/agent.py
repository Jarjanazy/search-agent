"""Three-phase research agent using the Anthropic Python SDK."""

from __future__ import annotations

import time
from datetime import date
from typing import Callable

import anthropic

MAX_RESEARCH_ITERATIONS = 20
MAX_TOKENS = 4096
_PLANNING_MAX_TOKENS = 1024
_RETRY_ATTEMPTS = 5
_INTER_ITERATION_DELAY = 2

_PLANNING_SYSTEM_PROMPT = """You are a research strategist. Analyze the given topic and search angles, then produce a structured markdown search plan.

Output format:
## Search Strategy
### Priority Queries
1. "query one"
2. "query two"
### Angles to Cover
- angle: why it matters for this topic
### Source Priorities
- types of sources most useful for this topic
### Avoid
- what to skip or deprioritize

Output ONLY the search plan. No preamble or explanation."""

_RESEARCH_SYSTEM_PROMPT_TEMPLATE = """You are a research assistant executing a pre-defined search plan.

Rules:
- Follow the search plan provided in the conversation.
- Use fetch_url to read full articles when a snippet is insufficient.
{date_rule}- Only include facts explicitly stated in search results. Do not fabricate statistics.
- {language_instruction}
- search_x and search_reddit always use English regardless of language distribution.
- Do not exceed 10 web_search calls, 5 search_x calls, or 5 search_reddit calls total.
- When you have completed all planned searches, output only: "Research complete."
- Do NOT write a report. A separate synthesis step will handle that.
"""

_SYNTHESIS_SYSTEM_PROMPT = """You are a research writer. You will be given a conversation history containing research findings. Synthesize these findings into a comprehensive business intelligence report.

Rules:
- The very first character of your output MUST be `#` (the report title). Output nothing before it — no preamble, no transition.
- Only include facts explicitly stated in the research findings. Do not fabricate statistics.
- Every claim must be sourced. Inline-link each statement to its source URL using Markdown: `[statement](<url>)`. List all URLs in the Sources section as well.
- Omit sections entirely where no current data was found. Do not pad with background knowledge.
- FORBIDDEN in output: any sentence or bullet stating that something was "not found", "not reported", "not announced", "not confirmed", or "no X reported". If you lack data on a point, omit that point silently.
- In the Sources section, cite only the specific article URL you read. Never cite a listing page, index, topic page, or homepage.

Output format (strict):
1. H1 title.
2. One-paragraph executive summary (5 sentences max).
3. Key Findings — bullet points only, grouped under bold subheadings.
4. Sources — numbered list of URLs with one-line description each.
"""


def _language_instruction(langs: list[tuple[str, float]]) -> str:
    items = ", ".join(f"{code} ({round(w * 100)}%)" for code, w in langs)
    return (
        f"Distribute your web_search calls across these languages proportionally: {items}. "
        "Write each query in the language you select and pass that language code in the `language` parameter of web_search."
    )


def _make_research_system_prompt(
    langs: list[tuple[str, float]],
    start_date: date | None = None,
    end_date: date | None = None,
) -> str:
    date_rule = (
        f"- Focus on facts and events that occurred between {start_date} and {end_date}. "
        "You may include facts from outside this window only when they provide context that makes in-window findings more meaningful. "
        "If a source's content is primarily about events outside this window with no relevant context for it, skip that source entirely.\n"
        if start_date and end_date
        else ""
    )
    return _RESEARCH_SYSTEM_PROMPT_TEMPLATE.format(
        date_rule=date_rule,
        language_instruction=_language_instruction(langs),
    )


def _create_with_retry(
    client: anthropic.Anthropic,
    model: str,
    messages: list[dict],
    system_prompt: str,
    tool_schemas: list[dict] | None = None,
    max_tokens: int = MAX_TOKENS,
) -> anthropic.types.Message:
    delay = 60
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            kwargs: dict = {
                "model": model,
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": list(messages),
            }
            if tool_schemas:
                kwargs["tools"] = tool_schemas
            return client.messages.create(**kwargs)
        except anthropic.RateLimitError:
            if attempt == _RETRY_ATTEMPTS - 1:
                raise
            print(f"Rate limit hit. Waiting {delay}s before retry {attempt + 1}/{_RETRY_ATTEMPTS - 1}...")
            time.sleep(delay)
            delay = min(delay * 2, 300)
    raise RuntimeError("unreachable")


def plan(
    api_key: str,
    model: str,
    topic: str,
    angles: list[str],
    languages: list[tuple[str, float]] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> str:
    """Call the planner model once to produce a structured search plan.

    Returns:
        Markdown search plan string.
    """
    angles_text = "\n".join(f"- {a}" for a in angles)
    date_context = (
        f"\nDate window: {start_date} to {end_date}."
        if start_date and end_date
        else ""
    )
    client = anthropic.Anthropic(api_key=api_key)
    messages = [
        {
            "role": "user",
            "content": (
                f"Topic: {topic}{date_context}\n\n"
                f"Available search angles:\n{angles_text}\n\n"
                "Produce a structured search plan."
            ),
        }
    ]
    response = _create_with_retry(
        client, model, messages, _PLANNING_SYSTEM_PROMPT, max_tokens=_PLANNING_MAX_TOKENS
    )
    for block in response.content:
        if block.type == "text":
            return block.text
    return ""


def research(
    api_key: str,
    model: str,
    topic: str,
    angles: list[str],
    plan_text: str,
    tool_executor: Callable[[str, dict], str],
    tool_schemas: list[dict],
    languages: list[tuple[str, float]] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> list[dict]:
    """Run the research tool-calling loop using the given plan.

    Returns:
        Full conversation messages list (for use by synthesize()).

    Raises:
        RuntimeError: If MAX_RESEARCH_ITERATIONS is reached without end_turn.
        ValueError: If an unexpected stop_reason is returned by the API.
    """
    langs = languages or [("en", 1.0)]
    system_prompt = _make_research_system_prompt(langs, start_date, end_date)
    client = anthropic.Anthropic(api_key=api_key)

    messages: list[dict] = [
        {
            "role": "user",
            "content": (
                f"Research this topic: {topic}\n\n"
                f"Follow this search plan:\n{plan_text}"
            ),
        }
    ]

    for iteration in range(MAX_RESEARCH_ITERATIONS):
        if iteration > 0:
            time.sleep(_INTER_ITERATION_DELAY)
        response = _create_with_retry(client, model, messages, system_prompt, tool_schemas)
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason in ("end_turn", "max_tokens"):
            return messages

        if response.stop_reason == "tool_use":
            tool_result_blocks = []
            for block in response.content:
                if block.type == "tool_use":
                    try:
                        result_str = tool_executor(block.name, block.input)
                    except Exception as exc:
                        result_str = f"Error executing tool {block.name}: {exc}"
                    tool_result_blocks.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result_str,
                        }
                    )
            if not tool_result_blocks:
                raise ValueError("stop_reason='tool_use' but no tool_use blocks in response")
            messages.append({"role": "user", "content": tool_result_blocks})
            continue

        raise ValueError(f"Unexpected stop_reason: {response.stop_reason!r}")

    raise RuntimeError(f"Max iterations ({MAX_RESEARCH_ITERATIONS}) reached without end_turn")


def synthesize(
    api_key: str,
    model: str,
    messages: list[dict],
) -> str:
    """Call the synthesis model to write the final report from research messages.

    Returns:
        Markdown report string.
    """
    client = anthropic.Anthropic(api_key=api_key)
    synthesis_messages = list(messages) + [
        {"role": "user", "content": "Write the final report now."}
    ]
    response = _create_with_retry(client, model, synthesis_messages, _SYNTHESIS_SYSTEM_PROMPT)
    for block in response.content:
        if block.type == "text":
            return block.text
    return ""
