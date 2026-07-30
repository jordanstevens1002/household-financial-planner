"""Host-only local administrator recovery."""

from datetime import timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.passwords import hash_password
from app.accounts.sessions import utc_now
from app.accounts.usernames import normalise_username
from app.core.config import Settings
from app.core.logging import get_logger
from app.models import (
    ApplicationSession,
    ApplicationUser,
    GlobalRole,
    PasswordResetToken,
)

logger = get_logger(component="operator_recovery")


async def recover_local_admin(
    database: AsyncSession,
    username: str,
    temporary_password: str,
    settings: Settings,
) -> ApplicationUser:
    """Restore one local account without exposing recovery through HTTP."""
    user = await database.scalar(
        select(ApplicationUser)
        .where(ApplicationUser.username == normalise_username(username))
        .with_for_update()
    )
    if user is None:
        raise ValueError("Local user not found")
    now = utc_now()
    user.password_hash = hash_password(temporary_password)
    user.global_role = GlobalRole.ADMIN
    user.is_active = True
    user.must_change_password = True
    user.password_expires_at = now + timedelta(hours=settings.temp_password_hours)
    await database.execute(
        delete(ApplicationSession).where(ApplicationSession.application_user_id == user.id)
    )
    await database.execute(
        delete(PasswordResetToken).where(PasswordResetToken.application_user_id == user.id)
    )
    await database.commit()
    logger.warning(
        "operator_admin_recovery_completed",
        target_user_id=str(user.id),
        target_username=user.username,
        forced_password_change=True,
    )
    return user
