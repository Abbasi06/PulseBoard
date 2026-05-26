"""
Content Pipeline — orchestrates fetch → filter → summarise → cache.

All LLM calls are synchronous (llama-cpp-python is blocking).
The pipeline runs in a thread via asyncio.to_thread so it never blocks
the FastAPI event loop.

Feed pipeline
─────────────
1. Build queries from user profile
2. DuckDuckGo search (all queries)
3. Relevance score each result (LLM, 1-10) — keep ≥ 6
4. Personalised 2-sentence summary (LLM) for top 15
5. Return list[dict] ready for SQLite insertion

Events pipeline
───────────────
1. Build event-focused queries
2. DuckDuckGo search
3. LLM extracts structured event fields (name/date/location/type/reason)
4. Return list[dict]
"""
from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any

from content.fetcher import build_event_queries, build_feed_queries, search
from llm.engine import LLMEngine
from models import User

logger = logging.getLogger(__name__)

_RELEVANCE_THRESHOLD = 6
_MAX_TO_SUMMARISE = 15
_MAX_FEED_ITEMS = 20
_MAX_EVENTS = 10
_TODAY = date.today().isoformat()


# ── Feed pipeline ─────────────────────────────────────────────────────────────


def run_feed_pipeline(user: User) -> list[dict[str, Any]]:
    """
    Synchronous full pipeline. Returns feed items ready to insert into SQLite.
    Returns empty list if LLM not ready or no results found.
    """
    engine = LLMEngine.get()
    if not engine.is_ready():
        logger.warning("LLM not ready — skipping feed pipeline for user %d", user.id)
        return []

    occupation: str = getattr(user, "occupation", "") or ""
    field: str = getattr(user, "field", "") or ""
    sub_fields: list[str] = list(getattr(user, "sub_fields", None) or [])
    chips: list[str] = list(getattr(user, "selected_chips", None) or [])
    excluded: list[str] = list(getattr(user, "excluded_topics", None) or [])
    interests = sub_fields if sub_fields else chips

    queries = build_feed_queries(user)
    raw = search(queries)

    if not raw:
        logger.info("No DDG results for user %d", user.id)
        return []

    # Filter by excluded topics (simple substring match — no LLM needed)
    if excluded:
        excluded_lower = [t.lower() for t in excluded]
        raw = [
            r for r in raw
            if not any(ex in r["title"].lower() or ex in r["snippet"].lower() for ex in excluded_lower)
        ]

    # Relevance scoring
    scored: list[tuple[int, dict[str, Any]]] = []
    for item in raw:
        score = engine.score_relevance(item["title"], item["snippet"], occupation, interests)
        if score >= _RELEVANCE_THRESHOLD:
            scored.append((score, item))
        logger.debug("relevance=%d %s", score, item["title"][:60])

    # Sort descending by score, cap
    scored.sort(key=lambda x: x[0], reverse=True)
    candidates = [item for _, item in scored[:_MAX_TO_SUMMARISE]]

    if not candidates:
        logger.info("No items passed relevance filter for user %d", user.id)
        return []

    # Personalised summarisation
    items: list[dict[str, Any]] = []
    for item in candidates:
        summary = engine.summarize(item["title"], item["snippet"], occupation, interests)
        topic = _infer_topic(item["title"], item["snippet"], field, interests)
        items.append({
            "user_id": user.id,
            "title": item["title"] or "Untitled",
            "summary": summary or item["snippet"][:300],
            "source": _extract_source(item["url"]),
            "url": item["url"],
            "topic": topic,
            "image_url": "",
            "published_date": _TODAY,
        })
        if len(items) >= _MAX_FEED_ITEMS:
            break

    logger.info("Feed pipeline complete for user %d: %d items", user.id, len(items))
    return items


# ── Events pipeline ───────────────────────────────────────────────────────────


def run_events_pipeline(user: User) -> list[dict[str, Any]]:
    """Synchronous events pipeline. Returns events ready for SQLite insertion."""
    engine = LLMEngine.get()
    if not engine.is_ready():
        logger.warning("LLM not ready — skipping events pipeline for user %d", user.id)
        return []

    queries = build_event_queries(user)
    raw = search(queries, max_per_query=6)

    if not raw:
        return []

    events: list[dict[str, Any]] = []
    for item in raw:
        parsed = _parse_event(engine, item, user)
        if parsed:
            events.append({**parsed, "user_id": user.id})
        if len(events) >= _MAX_EVENTS:
            break

    logger.info("Events pipeline complete for user %d: %d events", user.id, len(events))
    return events


def _parse_event(engine: LLMEngine, item: dict[str, Any], user: User) -> dict[str, Any] | None:
    """Ask LLM to extract event fields. Returns None if not a real event."""
    occupation = getattr(user, "occupation", "") or ""
    messages = [
        {
            "role": "system",
            "content": (
                "Extract event details from the article. "
                "Respond in this exact format:\n"
                "NAME: <event name>\n"
                "DATE: <date or 'Unknown'>\n"
                "LOCATION: <city/online or 'Unknown'>\n"
                "TYPE: <Conference|Workshop|Meetup|Webinar|Other>\n"
                "REASON: <one sentence why relevant to user>\n"
                "If this is not an event, respond with: NOT_EVENT"
            ),
        },
        {
            "role": "user",
            "content": (
                f"User: {occupation}\n"
                f"Title: {item['title']}\n"
                f"Content: {item['snippet'][:500]}"
            ),
        },
    ]
    raw = engine.chat(messages, max_tokens=120, temperature=0.1)
    if not raw or "NOT_EVENT" in raw:
        return None

    def _extract(label: str) -> str:
        m = re.search(rf"{label}:\s*(.+)", raw, re.IGNORECASE)
        return m.group(1).strip() if m else ""

    name = _extract("NAME")
    event_date = _extract("DATE")
    if not name or not event_date or event_date.lower() == "unknown":
        return None

    return {
        "name": name,
        "date": event_date,
        "location": _extract("LOCATION"),
        "type": _extract("TYPE") or "Other",
        "url": item["url"],
        "reason": _extract("REASON"),
        "image_url": "",
    }


# ── Helpers ───────────────────────────────────────────────────────────────────


def _extract_source(url: str) -> str:
    """Pull readable domain from URL, e.g. 'techcrunch.com'."""
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc
        return host.removeprefix("www.") if host else "Unknown"
    except Exception:
        return "Unknown"


def _infer_topic(title: str, snippet: str, field: str, interests: list[str]) -> str:
    """Lightweight topic label — keyword match against interests, no LLM call."""
    combined = (title + " " + snippet).lower()
    for interest in interests:
        if interest.lower() in combined:
            return interest.title()
    return field.title() if field else "General"
