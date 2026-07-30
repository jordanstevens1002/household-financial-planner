"""Bootstrap and local browser-session endpoints."""

import hmac
import math
from datetime import timedelta

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.passwords import hash_password, password_hash_needs_rehash, verify_password
from app.accounts.schemas import (
    AccountResponse,
    BootstrapRequest,
    BootstrapStatusResponse,
    Credentials,
    PasswordChangeRequest,
    PasswordResetRequest,
    SessionResponse,
)
from app.accounts.sessions import (
    as_utc,
    clear_session_cookies,
    create_session,
    resolve_session,
    set_session_cookies,
    utc_now,
)
from app.accounts.tokens import hash_token
from app.accounts.usernames import normalise_username
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.logging import get_logger
from app.models import (
    ApplicationSession,
    ApplicationUser,
    GlobalRole,
    LoginThrottle,
    PasswordResetToken,
)

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
DUMMY_PASSWORD_HASH = hash_password("authentication timing comparison only")
logger = get_logger(component="authentication")


def account_response(user: ApplicationUser) -> AccountResponse:
    assert user.username is not None
    return AccountResponse(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        email=user.email,
        global_role=user.global_role,
        must_change_password=user.must_change_password,
    )


async def bootstrap_required(database: AsyncSession) -> bool:
    local_accounts = await database.scalar(
        select(func.count(ApplicationUser.id)).where(ApplicationUser.username.is_not(None))
    )
    return not bool(local_accounts)


@router.get("/status", response_model=BootstrapStatusResponse)
async def auth_status(
    database: AsyncSession = Depends(get_session),
) -> BootstrapStatusResponse:
    return BootstrapStatusResponse(bootstrap_required=await bootstrap_required(database))


@router.post("/bootstrap", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def bootstrap(
    payload: BootstrapRequest,
    response: Response,
    bootstrap_token: str | None = Header(default=None, alias="X-Bootstrap-Token"),
    database: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> SessionResponse:
    configured = settings.local_auth_bootstrap_token
    if (
        configured is None
        or bootstrap_token is None
        or not hmac.compare_digest(bootstrap_token, configured.get_secret_value())
    ):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Invalid bootstrap token")
    if not await bootstrap_required(database):
        raise HTTPException(status.HTTP_409_CONFLICT, "Bootstrap has already completed")
    user = ApplicationUser(
        username=payload.username,
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        email=payload.email,
        global_role=GlobalRole.ADMIN,
    )
    database.add(user)
    await database.flush()
    created = await create_session(user, database, settings)
    set_session_cookies(response, created, settings)
    return SessionResponse(account=account_response(user), csrf_token=created.csrf_token)


def rate_limit_error(seconds: int) -> HTTPException:
    return HTTPException(
        status.HTTP_429_TOO_MANY_REQUESTS,
        "Too many failed login attempts",
        headers={"Retry-After": str(max(1, seconds))},
    )


async def record_login_failure(username: str, database: AsyncSession, settings: Settings) -> None:
    now = utc_now()
    throttle = await database.scalar(
        select(LoginThrottle).where(LoginThrottle.username == username)
    )
    window = timedelta(minutes=settings.login_block_minutes)
    if throttle is None:
        throttle = LoginThrottle(username=username, failed_attempts=0, window_started_at=now)
        database.add(throttle)
    elif now - as_utc(throttle.window_started_at) >= window:
        throttle.failed_attempts = 0
        throttle.window_started_at = now
        throttle.blocked_until = None
    throttle.failed_attempts += 1
    if throttle.failed_attempts >= settings.login_max_attempts:
        throttle.blocked_until = now + window
    await database.commit()


@router.post("/login", response_model=SessionResponse)
async def login(
    payload: Credentials,
    response: Response,
    database: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> SessionResponse:
    username = normalise_username(payload.username)
    throttle = await database.scalar(
        select(LoginThrottle).where(LoginThrottle.username == username)
    )
    now = utc_now()
    if throttle is not None and throttle.blocked_until is not None:
        blocked_until = as_utc(throttle.blocked_until)
        if blocked_until > now:
            raise rate_limit_error(math.ceil((blocked_until - now).total_seconds()))
    user = await database.scalar(
        select(ApplicationUser).where(ApplicationUser.username == username)
    )
    candidate_hash = user.password_hash if user and user.password_hash else DUMMY_PASSWORD_HASH
    password_matches = verify_password(candidate_hash, payload.password)
    valid = bool(user and user.is_active and user.password_hash and password_matches)
    if (
        valid
        and user is not None
        and user.password_expires_at is not None
        and as_utc(user.password_expires_at) <= now
    ):
        valid = False
    if not valid:
        await record_login_failure(username, database, settings)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")
    assert user is not None and user.password_hash is not None
    if password_hash_needs_rehash(user.password_hash):
        user.password_hash = hash_password(payload.password)
    await database.execute(delete(LoginThrottle).where(LoginThrottle.username == username))
    created = await create_session(user, database, settings)
    set_session_cookies(response, created, settings)
    return SessionResponse(account=account_response(user), csrf_token=created.csrf_token)


@router.get("/session", response_model=SessionResponse)
async def current_session(
    request: Request,
    database: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> SessionResponse:
    resolved = await resolve_session(request, database, settings, require_csrf=False)
    if resolved is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    user, _ = resolved
    return SessionResponse(account=account_response(user))


@router.post("/password/reset", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    payload: PasswordResetRequest,
    database: AsyncSession = Depends(get_session),
) -> None:
    now = utc_now()
    user_id = await database.scalar(
        update(PasswordResetToken)
        .where(
            PasswordResetToken.token_hash == hash_token(payload.token),
            PasswordResetToken.used_at.is_(None),
            PasswordResetToken.expires_at > now,
        )
        .values(used_at=now)
        .returning(PasswordResetToken.application_user_id)
        .execution_options(synchronize_session=False)
    )
    if user_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Reset token is invalid or expired")
    user = await database.get(ApplicationUser, user_id)
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Reset token is invalid or expired")
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    user.password_expires_at = None
    await database.execute(
        delete(ApplicationSession).where(ApplicationSession.application_user_id == user.id)
    )
    await database.commit()
    logger.info("password_reset_completed", target_user_id=str(user.id))


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    database: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> None:
    resolved = await resolve_session(request, database, settings)
    if resolved is not None:
        _, record = resolved
        record.revoked_at = utc_now()
        await database.commit()
    clear_session_cookies(response, settings)


@router.post("/password/change", response_model=SessionResponse)
async def change_password(
    payload: PasswordChangeRequest,
    request: Request,
    database: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> SessionResponse:
    resolved = await resolve_session(request, database, settings)
    if resolved is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Authentication required")
    user, current = resolved
    if user.password_hash is None or not verify_password(
        user.password_hash, payload.current_password
    ):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    user.password_expires_at = None
    await database.execute(
        delete(ApplicationSession).where(
            ApplicationSession.application_user_id == user.id,
            ApplicationSession.id != current.id,
        )
    )
    await database.commit()
    return SessionResponse(account=account_response(user))
