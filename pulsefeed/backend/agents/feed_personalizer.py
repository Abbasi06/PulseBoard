"""
Feed Personalizer — async entry points called by feed.py and events.py routes.

The heavy work (DDG search + LLM inference) is synchronous and runs in a
thread-pool executor via asyncio.to_thread so the FastAPI event loop stays free.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from sqlalchemy.orm import Session

from content.pipeline import run_events_pipeline, run_feed_pipeline
from models import User

logger = logging.getLogger(__name__)


async def personalize_feed(user_id: int, db: Session) -> list[dict[str, Any]]:
    """Async feed personalisation entry point — called by routes/feed.py."""
    user = db.get(User, user_id)
    if user is None:
        raise ValueError(f"User {user_id} not found")
    return await asyncio.to_thread(run_feed_pipeline, user)


async def personalize_events(user_id: int, db: Session) -> list[dict[str, Any]]:
    """Async events personalisation entry point — called by routes/events.py."""
    user = db.get(User, user_id)
    if user is None:
        raise ValueError(f"User {user_id} not found")
    return await asyncio.to_thread(run_events_pipeline, user)


