"""Global account administration endpoints."""

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.passwords import hash_password
from app.accounts.sessions import utc_now
from app.accounts.tokens import generate_token, hash_token
from app.admin.schemas import (
    AdminUserCreate,
    AdminUserCreated,
    AdminUserResponse,
    AdminUserUpdate,
    PasswordResetIssued,
)
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.dependencies import require_global_admin
from app.core.logging import get_logger
from app.models import (
    ApplicationSession,
    ApplicationUser,
    GlobalRole,
    PasswordResetToken,
)

router = APIRouter(prefix="/api/v1/admin", tags=["administration"])
logger = get_logger(component="account_administration")


def response_for(user: ApplicationUser) -> AdminUserResponse:
    assert user.username is not None
    return AdminUserResponse.model_validate(user, from_attributes=True)


async def ensure_another_active_admin(target: ApplicationUser, database: AsyncSession) -> None:
    if not target.is_active or target.global_role != GlobalRole.ADMIN:
        return
    active_admin_ids = (
        await database.scalars(
            select(ApplicationUser.id)
            .where(
                ApplicationUser.username.is_not(None),
                ApplicationUser.is_active.is_(True),
                ApplicationUser.global_role == GlobalRole.ADMIN,
            )
            .with_for_update()
        )
    ).all()
    if not any(user_id != target.id for user_id in active_admin_ids):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The final active administrator cannot be disabled or demoted",
        )


@router.get("/users", response_model=list[AdminUserResponse])
async def list_users(
    _: ApplicationUser = Depends(require_global_admin),
    database: AsyncSession = Depends(get_session),
) -> list[AdminUserResponse]:
    users = (
        await database.scalars(
            select(ApplicationUser)
            .where(ApplicationUser.username.is_not(None))
            .order_by(ApplicationUser.username)
        )
    ).all()
    return [response_for(user) for user in users]


@router.post("/users", response_model=AdminUserCreated, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: AdminUserCreate,
    actor: ApplicationUser = Depends(require_global_admin),
    database: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> AdminUserCreated:
    temporary_password = generate_token()
    expires_at = utc_now() + timedelta(hours=settings.temp_password_hours)
    user = ApplicationUser(
        username=payload.username,
        password_hash=hash_password(temporary_password),
        display_name=payload.display_name,
        email=payload.email,
        global_role=payload.global_role,
        must_change_password=True,
        password_expires_at=expires_at,
    )
    database.add(user)
    try:
        await database.commit()
    except IntegrityError as exc:
        await database.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already exists") from exc
    await database.refresh(user)
    logger.info(
        "admin_user_created",
        actor_user_id=str(actor.id),
        target_user_id=str(user.id),
        target_global_role=user.global_role,
    )
    return AdminUserCreated(account=response_for(user), temporary_password=temporary_password)


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
async def update_user(
    user_id: uuid.UUID,
    payload: AdminUserUpdate,
    actor: ApplicationUser = Depends(require_global_admin),
    database: AsyncSession = Depends(get_session),
) -> AdminUserResponse:
    user = await database.get(ApplicationUser, user_id)
    if user is None or user.username is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Local user not found")
    demoting = payload.global_role is not None and payload.global_role != GlobalRole.ADMIN
    disabling = payload.is_active is False
    if demoting or disabling:
        await ensure_another_active_admin(user, database)
    for field in payload.model_fields_set:
        setattr(user, field, getattr(payload, field))
    if disabling:
        await database.execute(
            delete(ApplicationSession).where(ApplicationSession.application_user_id == user.id)
        )
    try:
        await database.commit()
    except IntegrityError as exc:
        await database.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Username already exists") from exc
    await database.refresh(user)
    logger.info(
        "admin_user_updated",
        actor_user_id=str(actor.id),
        target_user_id=str(user.id),
        changed_fields=sorted(payload.model_fields_set),
    )
    return response_for(user)


@router.post("/users/{user_id}/password-reset", response_model=PasswordResetIssued)
async def issue_password_reset(
    user_id: uuid.UUID,
    actor: ApplicationUser = Depends(require_global_admin),
    database: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> PasswordResetIssued:
    user = await database.get(ApplicationUser, user_id)
    if user is None or user.username is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Local user not found")
    if not user.is_active:
        raise HTTPException(status.HTTP_409_CONFLICT, "Cannot reset a disabled user")
    now = utc_now()
    await database.execute(
        delete(PasswordResetToken).where(
            PasswordResetToken.application_user_id == user.id,
            PasswordResetToken.used_at.is_(None),
        )
    )
    await database.execute(
        delete(ApplicationSession).where(ApplicationSession.application_user_id == user.id)
    )
    raw_token = generate_token()
    expires_at = now + timedelta(minutes=settings.reset_token_minutes)
    database.add(
        PasswordResetToken(
            application_user_id=user.id,
            token_hash=hash_token(raw_token),
            expires_at=expires_at,
        )
    )
    await database.commit()
    logger.info(
        "admin_password_reset_issued",
        actor_user_id=str(actor.id),
        target_user_id=str(user.id),
        expires_at=expires_at.isoformat(),
    )
    return PasswordResetIssued(
        reset_path=f"/reset-password?token={raw_token}",
        expires_at=expires_at,
    )
