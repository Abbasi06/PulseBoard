import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from auth import get_current_user_id
from database import get_db
from models import FeedBrief, FeedItem, User
from schemas import BriefRead, FeedRead
from security.rate_limiter import feed_rate_limit, refresh_rate_limit, telemetry_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feed", tags=["feed"])

DEFAULT_CACHE_TTL_HOURS = 6
REFRESH_COOLDOWN_SECONDS = 60

# In-memory cooldown tracker (per-process; acceptable for single-server dev)
_last_refresh: dict[int, float] = {}

# Tracks user IDs whose feed is currently being generated in the background
_generating: set[int] = set()


def _get_user_ttl(user_id: int, db: Session) -> int:
    """Return the user's configured refresh interval in hours (defaults to 6)."""
    user = db.get(User, user_id)
    if user is None:
        return DEFAULT_CACHE_TTL_HOURS
    return int(getattr(user, "refresh_interval_hours", DEFAULT_CACHE_TTL_HOURS))


def _is_stale(fetched_at: datetime, ttl_hours: int) -> bool:
    age = datetime.now(timezone.utc) - fetched_at.replace(tzinfo=timezone.utc)
    return age > timedelta(hours=ttl_hours)


def _is_cache_warm(user_id: int, db: Session) -> bool:
    """Return True if the newest feed item is within the user's cache TTL."""
    ttl_hours = _get_user_ttl(user_id, db)
    latest_at = (
        db.query(func.max(FeedItem.fetched_at))
        .filter(FeedItem.user_id == user_id)
        .scalar()
    )
    return latest_at is not None and not _is_stale(latest_at, ttl_hours)


def _check_cooldown(user_id: int) -> None:
    last = _last_refresh.get(user_id, 0.0)
    elapsed = time.monotonic() - last
    if elapsed < REFRESH_COOLDOWN_SECONDS:
        remaining = int(REFRESH_COOLDOWN_SECONDS - elapsed)
        raise HTTPException(
            status_code=429,
            detail=f"Refresh too soon — wait {remaining}s before trying again",
            headers={"Retry-After": str(remaining)},
        )


def _save_items(items: list[dict], db: Session) -> None:
    for item in items:
        db.add(
            FeedItem(
                user_id=item["user_id"],
                title=item["title"],
                summary=item["summary"],
                source=item["source"],
                url=item["url"],
                topic=item["topic"],
                image_url=item.get("image_url", ""),
                published_date=item.get("published_date", ""),
            )
        )
    db.commit()


@router.get("/{user_id}", response_model=list[FeedRead], dependencies=[Depends(feed_rate_limit)])
async def get_feed(
    user_id: int,
    background_tasks: BackgroundTasks,
    response: Response,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[FeedItem]:
    if user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")

    if _is_cache_warm(user_id, db):
        return (
            db.query(FeedItem)
            .filter(FeedItem.user_id == user_id)
            .order_by(FeedItem.fetched_at.desc())
            .all()
        )

    # Cache is cold — return existing items immediately and generate in background
    existing = (
        db.query(FeedItem)
        .filter(FeedItem.user_id == user_id)
        .order_by(FeedItem.fetched_at.desc())
        .all()
    )
    if user_id not in _generating:
        _generating.add(user_id)
        background_tasks.add_task(_background_refresh, user_id)
    response.headers["X-Feed-Generating"] = "true"
    return existing


@router.post("/{user_id}/refresh", response_model=list[FeedRead], dependencies=[Depends(refresh_rate_limit)])
async def refresh_feed(
    user_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> list[FeedItem]:
    if user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")
    _check_cooldown(user_id)
    _last_refresh[user_id] = time.monotonic()
    result = await _refresh_feed(user_id, db)
    return result


@router.get("/{user_id}/brief", response_model=BriefRead)
async def get_brief(
    user_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> FeedBrief:
    if user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    if db.get(User, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")

    has_feed = (
        db.query(FeedItem.id).filter(FeedItem.user_id == user_id).limit(1).scalar()
    )
    if not has_feed:
        raise HTTPException(
            status_code=404, detail="No feed items — generate feed first"
        )

    brief = db.query(FeedBrief).filter(FeedBrief.user_id == user_id).first()
    ttl_hours = _get_user_ttl(user_id, db)
    if brief and not _is_stale(brief.generated_at, ttl_hours):
        return brief

    return await _refresh_brief(user_id, db)


@router.patch("/items/{item_id}/like", response_model=FeedRead)
def toggle_like(
    item_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> FeedItem:
    item = db.get(FeedItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Feed item not found")
    if item.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    item.liked = not item.liked
    db.commit()
    db.refresh(item)
    return item


@router.patch("/items/{item_id}/dislike", response_model=FeedRead)
def toggle_dislike(
    item_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> FeedItem:
    item = db.get(FeedItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Feed item not found")
    if item.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    item.disliked = not item.disliked
    db.commit()
    db.refresh(item)
    return item


@router.patch("/items/{item_id}/save", response_model=FeedRead)
def toggle_save(
    item_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> FeedItem:
    item = db.get(FeedItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Feed item not found")
    if item.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    item.saved = not item.saved
    db.commit()
    db.refresh(item)
    return item


@router.post("/items/{item_id}/click", response_model=FeedRead, dependencies=[Depends(telemetry_rate_limit)])
def record_click(
    item_id: int,
    current_user_id: int = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> FeedItem:
    item = db.get(FeedItem, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Feed item not found")
    if item.user_id != current_user_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    item.read_count += 1
    db.commit()
    db.refresh(item)
    return item


_GENERATION_TIMEOUT = 180  # seconds


async def _background_refresh(user_id: int) -> None:
    """Background feed refresh — creates its own DB session so it outlives the request."""
    from agents.feed_personalizer import personalize_feed
    from database import engine
    from sqlalchemy.orm import Session as SASession

    db = SASession(engine)
    try:
        items = await asyncio.wait_for(personalize_feed(user_id, db), timeout=_GENERATION_TIMEOUT)
        if not items:
            logger.warning(
                "Background refresh returned 0 items for user %d — generator pool empty, keeping existing feed",
                user_id,
            )
            return
        # Only replace once we have confirmed items to store
        db.query(FeedItem).filter(FeedItem.user_id == user_id).delete()
        db.query(FeedBrief).filter(FeedBrief.user_id == user_id).delete()
        _save_items(items, db)
        logger.info(
            "Background feed refresh complete for user %d: %d items stored",
            user_id,
            len(items),
        )
    except asyncio.TimeoutError:
        logger.error(
            "Background feed refresh timed out after %ds for user %d",
            _GENERATION_TIMEOUT,
            user_id,
        )
    except Exception as exc:
        logger.error("Background feed refresh failed for user %d: %s", user_id, exc, exc_info=True)
    finally:
        db.close()
        _generating.discard(user_id)


async def _refresh_feed(user_id: int, db: Session) -> list[FeedItem]:
    from agents.feed_personalizer import personalize_feed

    try:
        items = await asyncio.wait_for(personalize_feed(user_id, db), timeout=_GENERATION_TIMEOUT)
    except asyncio.TimeoutError as exc:
        logger.error("Feed generation timed out for user %d", user_id)
        raise HTTPException(status_code=504, detail="Feed generation timed out") from exc
    except Exception as exc:
        logger.error("personalize_feed failed for user %d: %s", user_id, exc, exc_info=True)
        raise HTTPException(status_code=502, detail="Feed generation failed") from exc

    if not items:
        logger.info("Generator pool empty for user %d — returning existing feed", user_id)
        return (
            db.query(FeedItem)
            .filter(FeedItem.user_id == user_id)
            .order_by(FeedItem.fetched_at.desc())
            .all()
        )

    db.query(FeedItem).filter(FeedItem.user_id == user_id).delete()
    db.query(FeedBrief).filter(FeedBrief.user_id == user_id).delete()
    _save_items(items, db)

    new_items = (
        db.query(FeedItem)
        .filter(FeedItem.user_id == user_id)
        .order_by(FeedItem.fetched_at.desc())
        .all()
    )
    logger.info("Feed refreshed for user %d: %d items stored", user_id, len(new_items))
    return new_items


async def _refresh_brief(user_id: int, db: Session) -> FeedBrief:
    """Generate a feed brief from existing feed items — no external AI call."""
    items = (
        db.query(FeedItem)
        .filter(FeedItem.user_id == user_id)
        .order_by(FeedItem.fetched_at.desc())
        .limit(5)
        .all()
    )

    top_reads = [
        {"title": item.title, "url": item.url, "source": item.source}
        for item in items[:3]
    ]
    topics = list(dict.fromkeys(item.topic for item in items if item.topic and item.topic != "General"))

    db.query(FeedBrief).filter(FeedBrief.user_id == user_id).delete()
    brief = FeedBrief(
        user_id=user_id,
        headline="Today's curated highlights from PulseFeed",
        signals=topics[:5],
        top_reads=top_reads,
        watch=[],
    )
    db.add(brief)
    db.commit()
    db.refresh(brief)
    return brief
