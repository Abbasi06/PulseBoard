"""
Content Fetcher — builds search queries from user profile and fetches
results from DuckDuckGo text search.

No API key required. Rate-limited by DuckDuckGo's own throttle; we add
small sleeps between queries to stay well within limits.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from duckduckgo_search import DDGS

from models import User

logger = logging.getLogger(__name__)

_MAX_RESULTS_PER_QUERY = 8
_QUERY_SLEEP_SECONDS = 0.8   # polite pause between DDG requests


# ── Query builders ────────────────────────────────────────────────────────────


def build_feed_queries(user: User) -> list[str]:
    """Generate 3-5 DuckDuckGo queries from the user profile."""
    occupation: str = getattr(user, "occupation", "") or ""
    field: str = getattr(user, "field", "") or ""
    sub_fields: list[str] = list(getattr(user, "sub_fields", None) or [])
    chips: list[str] = list(getattr(user, "selected_chips", None) or [])

    interests = sub_fields if sub_fields else chips
    queries: list[str] = []

    if field and occupation:
        queries.append(f"{field} {occupation} news")
    elif occupation:
        queries.append(f"{occupation} latest news")

    for interest in interests[:3]:
        queries.append(f"{interest} news update 2025")

    if field:
        queries.append(f"{field} breakthroughs research")

    return queries[:5]


def build_event_queries(user: User) -> list[str]:
    """Generate 2-3 DuckDuckGo queries for upcoming events."""
    occupation: str = getattr(user, "occupation", "") or ""
    field: str = getattr(user, "field", "") or ""
    sub_fields: list[str] = list(getattr(user, "sub_fields", None) or [])

    queries: list[str] = []
    if field:
        queries.append(f"{field} conferences 2025 upcoming")
    if occupation:
        queries.append(f"{occupation} events meetups 2025")
    if sub_fields:
        queries.append(f"{sub_fields[0]} summit workshop 2025")

    return queries[:3]


# ── DDG search ────────────────────────────────────────────────────────────────


def search(queries: list[str], max_per_query: int = _MAX_RESULTS_PER_QUERY) -> list[dict[str, Any]]:
    """
    Run all queries through DuckDuckGo text search.

    Returns deduplicated list of {"title", "url", "snippet"} dicts.
    Never raises — returns empty list on any failure.
    """
    seen_urls: set[str] = set()
    results: list[dict[str, Any]] = []

    try:
        with DDGS() as ddgs:
            for query in queries:
                try:
                    hits = ddgs.text(query, max_results=max_per_query)
                    for h in hits or []:
                        url = h.get("href", "")
                        if not url or url in seen_urls:
                            continue
                        seen_urls.add(url)
                        results.append({
                            "title": h.get("title", "").strip(),
                            "url": url,
                            "snippet": h.get("body", "").strip(),
                        })
                    time.sleep(_QUERY_SLEEP_SECONDS)
                except Exception as exc:
                    logger.warning("DDG query failed (%r): %s", query, exc)
    except Exception as exc:
        logger.error("DDG session error: %s", exc)

    return results
