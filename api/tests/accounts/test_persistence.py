import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.passwords import (
    hash_password,
    password_hash_needs_rehash,
    verify_password,
)
from app.accounts.tokens import hash_token
from app.models import (
    ApplicationSession,
    ApplicationUser,
    GlobalRole,
    HouseholdMembership,
    LegacyIdentity,
    LegacyIdentityMapping,
    LoginThrottle,
    PasswordResetToken,
)


def test_passwords_use_argon2id_and_reject_invalid_credentials() -> None:
    password_hash = hash_password("correct horse battery staple")

    assert password_hash.startswith("$argon2id$")
    assert "correct horse battery staple" not in password_hash
    assert verify_password(password_hash, "correct horse battery staple")
    assert not verify_password(password_hash, "incorrect")
    assert not verify_password("not-a-hash", "incorrect")
    assert not password_hash_needs_rehash(password_hash)


def test_secret_tokens_are_stored_as_fixed_length_digests() -> None:
    token = "a-high-entropy-token-that-would-normally-come-from-secrets"
    digest = hash_token(token)

    assert len(digest) == 64
    assert token not in digest
    assert digest == hash_token(token)


async def test_local_usernames_are_canonical_and_unique(session: AsyncSession) -> None:
    with pytest.raises(ValueError, match="Username cannot be empty"):
        ApplicationUser(username="   ")

    administrator = ApplicationUser(
        username="  Ａlice  ",
        password_hash=hash_password("a password"),
        global_role=GlobalRole.ADMIN,
        is_active=True,
        must_change_password=False,
    )
    session.add(administrator)
    await session.commit()

    assert administrator.username == "alice"
    assert (
        await session.scalar(
            select(func.count(HouseholdMembership.id)).where(
                HouseholdMembership.application_user_id == administrator.id
            )
        )
        == 0
    )

    session.add(ApplicationUser(username="ALICE", global_role=GlobalRole.USER))
    with pytest.raises(IntegrityError):
        await session.commit()
    await session.rollback()


async def test_authentication_records_store_only_digests(session: AsyncSession) -> None:
    now = datetime.now(UTC)
    user = ApplicationUser(username="local-user", global_role=GlobalRole.USER)
    session.add(user)
    await session.flush()

    session_token = "raw-session-token"
    reset_token = "raw-reset-token"
    session.add_all(
        [
            ApplicationSession(
                application_user_id=user.id,
                session_token_hash=hash_token(session_token),
                csrf_token_hash=hash_token("raw-csrf-token"),
                last_seen_at=now,
                idle_expires_at=now + timedelta(hours=12),
                absolute_expires_at=now + timedelta(days=7),
            ),
            PasswordResetToken(
                application_user_id=user.id,
                token_hash=hash_token(reset_token),
                expires_at=now + timedelta(minutes=30),
            ),
            LoginThrottle(
                username=" LOCAL-USER ",
                failed_attempts=2,
                window_started_at=now,
            ),
        ]
    )
    await session.commit()

    stored_session = await session.scalar(select(ApplicationSession))
    stored_reset = await session.scalar(select(PasswordResetToken))
    throttle = await session.scalar(select(LoginThrottle))
    assert stored_session is not None
    assert stored_reset is not None
    assert throttle is not None
    assert stored_session.session_token_hash != session_token
    assert stored_reset.token_hash != reset_token
    assert throttle.username == "local-user"


async def test_legacy_mapping_is_auditable_without_transferring_membership(
    session: AsyncSession,
) -> None:
    legacy_user = ApplicationUser(
        oidc_subject="legacy-subject",
        email="old@example.com",
        global_role=GlobalRole.USER,
    )
    local_admin = ApplicationUser(
        username="administrator",
        password_hash=hash_password("a password"),
        global_role=GlobalRole.ADMIN,
    )
    local_user = ApplicationUser(
        username="mapped-user",
        password_hash=hash_password("a password"),
        global_role=GlobalRole.USER,
    )
    session.add_all([legacy_user, local_admin, local_user])
    await session.flush()

    identity = LegacyIdentity(
        source_application_user_id=legacy_user.id,
        oidc_subject=legacy_user.oidc_subject,
        email=legacy_user.email,
    )
    session.add(identity)
    await session.flush()
    mapping = LegacyIdentityMapping(
        legacy_identity_id=identity.id,
        application_user_id=local_user.id,
        mapped_by_application_user_id=local_admin.id,
    )
    session.add(mapping)
    await session.commit()

    assert mapping.id != uuid.UUID(int=0)
    assert mapping.application_user_id == local_user.id
    assert mapping.mapped_by_application_user_id == local_admin.id
    assert (
        await session.scalar(
            select(func.count(HouseholdMembership.id)).where(
                HouseholdMembership.application_user_id == local_admin.id
            )
        )
        == 0
    )
