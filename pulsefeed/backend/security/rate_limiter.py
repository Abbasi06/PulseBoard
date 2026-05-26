"""
In-process fixed-window rate limiter — no Redis required.

Keyed by (scope, identifier). Windows reset automatically as time advances.
For a single-server local app this is sufficient; the 60-second refresh
cooldown in feed.py / events.py provides the primary throttle.
"""
from __future__ import annotations

import logging
import time
import threading
from collections import defaultdict
from collections.abc import Awaitable, Callable

from fastapi import Depends, HTTPException, Request

logger = logging.getLogger(__name__)

_counters: dict[str, list[float]] = defaultdict(list)
_lock = threading.Lock()


def _check(scope: str, identifier: str, limit: int, window: int) -> None:
    now = time.monotonic()
    key = f"{scope}:{identifier}"
    with _lock:
        timestamps = [t for t in _counters[key] if now - t < window]
        timestamps.append(now)
        _counters[key] = timestamps
        count = len(timestamps)

    if count > limit:
        retry_after = window
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded ({limit} req/{window}s). Retry in {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )


# ── Dependency factories ──────────────────────────────────────────────────────


def _make_feed_dep() -> Callable[..., Awaitable[None]]:
    from auth import get_current_user_id

    async def _feed_rate_limit(
        request: Request,
        current_user_id: int = Depends(get_current_user_id),
    ) -> None:
        _check("feed_read", f"user:{current_user_id}", limit=30, window=60)

    return _feed_rate_limit


def _make_refresh_dep() -> Callable[..., Awaitable[None]]:
    from auth import get_current_user_id

    async def _refresh_rate_limit(
        request: Request,
        current_user_id: int = Depends(get_current_user_id),
    ) -> None:
        _check("feed_refresh", f"user:{current_user_id}", limit=3, window=60)

    return _refresh_rate_limit


async def registration_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    _check("registration", f"ip:{ip}", limit=5, window=60)


async def telemetry_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    _check("telemetry", f"ip:{ip}", limit=100, window=60)


feed_rate_limit: Callable[..., Awaitable[None]] = _make_feed_dep()
refresh_rate_limit: Callable[..., Awaitable[None]] = _make_refresh_dep()
