"""Server-side browser session lifecycle."""

import hmac
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.tokens import generate_token, hash_token
from app.core.config import Settings
from app.models import ApplicationSession, ApplicationUser

SESSION_COOKIE = "hfp_session"
CSRF_COOKIE = "hfp_csrf"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


@dataclass(frozen=True)
class CreatedSession:
    record: ApplicationSession
    session_token: str
    csrf_token: str


def utc_now() -> datetime:
    return datetime.now(UTC)


def as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


async def create_session(
    user: ApplicationUser,
    database: AsyncSession,
    settings: Settings,
) -> CreatedSession:
    now = utc_now()
    session_token = generate_token()
    csrf_token = generate_token()
    absolute_expiry = now + timedelta(hours=settings.session_absolute_hours)
    record = ApplicationSession(
        application_user_id=user.id,
        session_token_hash=hash_token(session_token),
        csrf_token_hash=hash_token(csrf_token),
        last_seen_at=now,
        idle_expires_at=min(
            now + timedelta(minutes=settings.session_idle_minutes), absolute_expiry
        ),
        absolute_expires_at=absolute_expiry,
    )
    database.add(record)
    await database.commit()
    await database.refresh(record)
    return CreatedSession(record, session_token, csrf_token)


def set_session_cookies(response: Response, created: CreatedSession, settings: Settings) -> None:
    max_age = settings.session_absolute_hours * 60 * 60
    response.set_cookie(
        SESSION_COOKIE,
        created.session_token,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
        max_age=max_age,
    )
    response.set_cookie(
        CSRF_COOKIE,
        created.csrf_token,
        httponly=False,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
        max_age=max_age,
    )


def clear_session_cookies(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        SESSION_COOKIE,
        path="/",
        secure=settings.session_cookie_secure,
        samesite="lax",
        httponly=True,
    )
    response.delete_cookie(
        CSRF_COOKIE,
        path="/",
        secure=settings.session_cookie_secure,
        samesite="lax",
        httponly=False,
    )


async def resolve_session(
    request: Request,
    database: AsyncSession,
    settings: Settings,
    *,
    require_csrf: bool = True,
) -> tuple[ApplicationUser, ApplicationSession] | None:
    raw_token = request.cookies.get(SESSION_COOKIE)
    if not raw_token:
        return None
    record = await database.scalar(
        select(ApplicationSession).where(
            ApplicationSession.session_token_hash == hash_token(raw_token)
        )
    )
    now = utc_now()
    if (
        record is None
        or record.revoked_at is not None
        or as_utc(record.idle_expires_at) <= now
        or as_utc(record.absolute_expires_at) <= now
    ):
        if record is not None and record.revoked_at is None:
            record.revoked_at = now
            await database.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired or invalid")
    user = await database.get(ApplicationUser, record.application_user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired or invalid")
    if require_csrf and request.method not in SAFE_METHODS:
        supplied = request.headers.get("X-CSRF-Token", "")
        if not hmac.compare_digest(hash_token(supplied), record.csrf_token_hash):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "CSRF token required or invalid")
    record.last_seen_at = now
    record.idle_expires_at = min(
        now + timedelta(minutes=settings.session_idle_minutes),
        as_utc(record.absolute_expires_at),
    )
    await database.commit()
    return user, record
