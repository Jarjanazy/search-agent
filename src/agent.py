"""Agentic loop for the research agent using the Anthropic Python SDK."""

from __future__ import annotations

import time
from datetime import date
from typing import Callable

import anthropic

MAX_ITERATIONS = 25
MAX_TOKENS = 4096
_RETRY_ATTEMPTS = 5

_SYSTEM_PROMPT_TEMPLATE = """You are a research assistant producing weekly business-intelligence reports.

Rules:
- The very first character of your output MUST be `#` (the report title). Output nothing before it — no preamble, no transition, no "I now have...", no "Let me...".
- {search_instruction} After completing your searches, write the full report in a single response — do not call any tools after that.
- Use fetch_url to read full articles when a snippet is insufficient.
{date_rule}- Only include facts explicitly stated in search results. Do not fabricate statistics.
- Every claim must be sourced. Inline-link each statement to its source URL using Markdown: `[statement](<url>)`. List all URLs in the Sources section as well.
- Omit sections entirely where no current data was found. Do not pad with background knowledge.
- FORBIDDEN in output: any sentence or bullet stating that something was "not found", "not reported", "not announced", "not confirmed", or "no X reported". If you lack data on a point, omit that point silently.
- In the Sources section, cite only the specific article URL you read. Never cite a listing page, index, topic page, or homepage. If you only found an index page, do not cite it.

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


def run_agent(
    anthropic_api_key: str,
    model: str,
    topic: str,
    tool_executor: Callable[[str, dict], str],
    tool_schemas: list[dict],
    search_angles: list[str],
    search_languages: list[tuple[str, float]] | None = None,
    search_start_date: date | None = None,
    search_end_date: date | None = None,
) -> str:
    """Run the research agent agentic loop.

    Args:
        anthropic_api_key: Anthropic API key for authentication.
        model: Model identifier to use (e.g. "claude-3-5-sonnet-20241022").
        topic: The research topic to investigate.
        tool_executor: Callable that accepts (tool_name, tool_input) and returns a string result.
        tool_schemas: List of tool schema dicts passed to the Anthropic API.

    Returns:
        The final text output from the model (Markdown report).

    Raises:
        RuntimeError: If MAX_ITERATIONS is reached without an end_turn stop reason.
        ValueError: If an unexpected stop_reason is returned by the API.
    """
    langs = search_languages or [("en", 1.0)]
    angles_list = "\n".join(f'- "{q}"' for q in search_angles)
    search_instruction = (
        "Use ONLY the following search angles, verbatim, in any order. "
        "Do not invent new query angles. "
        "For each angle, run all three of these tools using the exact angle text as the query: "
        "(1) web_search — general web results; "
        "(2) search_x — X (Twitter) posts and threads; "
        "(3) search_reddit — Reddit discussions. "
        f"{_language_instruction(langs)} "
        "web_search calls observe the language distribution above; search_x and search_reddit always use English. "
        "Do not exceed 10 web_search calls, 5 search_x calls, or 5 search_reddit calls total.\n\n"
        f"Angles:\n{angles_list}"
    )
    date_rule = (
        f"- Focus on facts and events that occurred between {search_start_date} and {search_end_date}. "
        "You may include facts from outside this window only when they provide context that makes in-window findings more meaningful. "
        "If a source's content is primarily about events outside this window with no relevant context for it, skip that source entirely.\n"
        if search_start_date and search_end_date
        else ""
    )
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
        search_instruction=search_instruction,
        date_rule=date_rule,
    )

    client = anthropic.Anthropic(api_key=anthropic_api_key)

    messages: list[dict] = [
        {"role": "user", "content": f"Research this topic and write a Markdown report: {topic}"}
    ]

    for _ in range(MAX_ITERATIONS):
        response = _create_with_retry(client, model, tool_schemas, messages, system_prompt)

        # Append assistant response to message history
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason in ("end_turn", "max_tokens"):
            # Extract and return the text block
            for block in response.content:
                if block.type == "text":
                    return block.text
            # Fallback: no text block found
            return ""

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

    raise RuntimeError(f"Max iterations ({MAX_ITERATIONS}) reached without end_turn")


def _create_with_retry(
    client: anthropic.Anthropic,
    model: str,
    tool_schemas: list[dict],
    messages: list[dict],
    system_prompt: str,
) -> anthropic.types.Message:
    delay = 60
    for attempt in range(_RETRY_ATTEMPTS):
        try:
            return client.messages.create(
                model=model,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                tools=tool_schemas,
                messages=list(messages),
            )
        except anthropic.RateLimitError:
            if attempt == _RETRY_ATTEMPTS - 1:
                raise
            print(f"Rate limit hit. Waiting {delay}s before retry {attempt + 1}/{_RETRY_ATTEMPTS - 1}...")
            time.sleep(delay)
            delay = min(delay * 2, 300)
    raise RuntimeError("unreachable")
