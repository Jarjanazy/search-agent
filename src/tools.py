"""Tool schemas and executor for the research agent."""

from __future__ import annotations

from typing import Callable

import httpx

TOOL_SCHEMAS = [
    {
        "name": "web_search",
        "description": (
            "Search the web for current information on a topic. "
            "Returns results with title, URL, and content snippet."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query string. Write this in the language specified by `language`.",
                },
                "language": {
                    "type": "string",
                    "description": (
                        "ISO 639-1 language code for both the query and result language "
                        "(e.g. 'en', 'ar', 'de'). Write the query in this language."
                    ),
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "fetch_url",
        "description": (
            "Fetch the full text content of a URL. "
            "Use when a search snippet is not enough."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch",
                }
            },
            "required": ["url"],
        },
    },
]


def make_tool_executor(
    brave_api_key: str,
    max_results: int,
) -> Callable[[str, dict], str]:
    """Return a tool executor bound to the given Brave API key and result limit."""

    def execute(tool_name: str, tool_input: dict) -> str:
        if tool_name == "web_search":
            lang = tool_input.get("language", "en")
            return _web_search(tool_input["query"], brave_api_key, max_results, lang)
        if tool_name == "fetch_url":
            return _fetch_url(tool_input["url"])
        raise ValueError(f"Unknown tool: {tool_name!r}")

    return execute


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _web_search(query: str, api_key: str, max_results: int, lang: str = "en") -> str:
    response = httpx.get(
        "https://api.search.brave.com/res/v1/web/search",
        params={"q": query, "count": max_results, "search_lang": lang},
        headers={
            "X-Subscription-Token": api_key,
            "Accept": "application/json",
        },
        timeout=10,
    )
    response.raise_for_status()
    data = response.json()
    results = data.get("web", {}).get("results", [])

    if not results:
        return "No results found."

    lines: list[str] = []
    for i, item in enumerate(results, start=1):
        title = item.get("title", "")
        url = item.get("url", "")
        description = item.get("description", "")
        lines.append(f"{i}. **{title}**\n   URL: {url}\n   Description: {description}\n")

    return "\n".join(lines)


def _fetch_url(url: str) -> str:
    response = httpx.get(url, timeout=15, follow_redirects=True)
    response.raise_for_status()
    return response.text[:8000]
