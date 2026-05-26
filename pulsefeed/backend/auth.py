"""
JWT helpers for PulseFeed.

Token is stored in an httpOnly cookie named `access_token`.

SameSite policy — controlled by COOKIE_SAMESITE env var:
  dev  (default) COOKIE_SAMESITE=lax
       Allows same-host cross-port (localhost:5173 → localhost:8000)
       without HTTPS.
  prod           COOKIE_SAMESITE=none + COOKIE_SECURE=true
       Required when the Vercel frontend POSTs to the VPS API across
       origins.  SameSite=Lax silently drops cookies on cross-site
       POST/PUT/DELETE, breaking auth entirely in production.
"""

import logging
import os
from datetime import datetime, timedelta, timezone

from fastapi import Cookie, HTTPException
from jose import JWTError, jwt

logger = logging.getLogger(__name__)

SECRET_KEY: str = os.environ.get("SECRET_KEY", "dev-secret-change-before-production")
ALGORITHM = "HS256"
TOKEN_EXPIRE_DAYS = 30

_samesite: str = os.environ.get("COOKIE_SAMESITE", "lax").lower()
_secure: bool = os.environ.get("COOKIE_SECURE", "false").lower() == "true"

if _samesite == "none" and not _secure:
    logger.warning(
        "COOKIE_SAMESITE=none requires COOKIE_SECURE=true — "
        "browsers will reject the auth cookie in production"
    )

COOKIE_OPTS: dict = dict(
    key="access_token",
    httponly=True,
    samesite=_samesite,
    secure=_secure,
    path="/",
    max_age=TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
)


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=TOKEN_EXPIRE_DAYS)
    return jwt.encode({"sub": str(user_id), "exp": expire}, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> int:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return int(payload["sub"])
    except (JWTError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc


def get_current_user_id(access_token: str | None = Cookie(default=None)) -> int:
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return _decode_token(access_token)
