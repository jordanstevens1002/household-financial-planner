"""Legacy OIDC identity migration API tests."""

import uuid
from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.passwords import verify_password
from app.accounts.sessions import utc_now
from app.models import (
    ApplicationUser,
    GlobalRole,
    Household,
    HouseholdMembership,
    HouseholdRole,
    LegacyIdentity,
    LegacyIdentityMapping,
)

from .test_admin_api import create_local_user
from .test_auth_api import bootstrap, configure, local_settings


async def legacy_households(
    session: AsyncSession,
) -> tuple[LegacyIdentity, Household, Household]:
    source = ApplicationUser(
        oidc_subject="legacy-person",
        display_name="Legacy Person",
        email="legacy@example.invalid",
    )
    first = Household(display_name="First Home", currency="NZD", jurisdiction="NZ")
    second = Household(display_name="Second Home", currency="CAD", jurisdiction="CA")
    session.add_all([source, first, second])
    await session.flush()
    identity = LegacyIdentity(
        source_application_user_id=source.id,
        oidc_subject=source.oidc_subject,
        display_name=source.display_name,
        email=source.email,
    )
    session.add_all(
        [
            identity,
            HouseholdMembership(
                household_id=first.id,
                application_user_id=source.id,
                role=HouseholdRole.VIEWER,
            ),
            HouseholdMembership(
                household_id=second.id,
                application_user_id=source.id,
                role=HouseholdRole.OWNER,
            ),
        ]
    )
    await session.commit()
    return identity, first, second


async def test_list_exposes_only_identity_and_household_mapping_context(
    client: AsyncClient, session: AsyncSession
) -> None:
    configure(local_settings())
    await bootstrap(client)
    identity, first, second = await legacy_households(session)

    response = await client.get("/api/v1/admin/legacy-identities")

    assert response.status_code == 200
    assert response.json()["unresolved_count"] == 1
    assert response.json()["activation_pending_count"] == 0
    assert response.json()["cutover_ready"] is False
    listed = response.json()["identities"]
    assert len(listed) == 1
    assert listed[0] == {
        "id": str(identity.id),
        "oidc_subject": "legacy-person",
        "email": "legacy@example.invalid",
        "display_name": "Legacy Person",
        "captured_at": listed[0]["captured_at"],
        "memberships": [
            {
                "household_id": str(first.id),
                "household_name": "First Home",
                "role": "VIEWER",
            },
            {
                "household_id": str(second.id),
                "household_name": "Second Home",
                "role": "OWNER",
            },
        ],
        "mapping": None,
        "status": "UNMAPPED",
    }
    assert "source_application_user_id" not in response.text
    assert "financial" not in response.text


async def test_mapping_existing_account_preserves_strongest_roles_and_is_auditable(
    client: AsyncClient, session: AsyncSession
) -> None:
    configure(local_settings())
    administrator = await bootstrap(client)
    identity, first, second = await legacy_households(session)
    created = await create_local_user(client, "mapped-person")
    target_id = uuid.UUID(created["account"]["id"])
    target = await session.get(ApplicationUser, target_id)
    assert target is not None
    target.must_change_password = False
    target.password_expires_at = None
    session.add(
        HouseholdMembership(
            household_id=first.id,
            application_user_id=target_id,
            role=HouseholdRole.ADMIN,
        )
    )
    await session.commit()

    response = await client.post(
        f"/api/v1/admin/legacy-identities/{identity.id}/mapping",
        headers={"X-CSRF-Token": client.cookies["hfp_csrf"]},
        json={"application_user_id": str(target_id)},
    )

    assert response.status_code == 201
    assert response.json()["temporary_password"] is None
    assert response.json()["identity"]["mapping"]["username"] == "mapped-person"
    assert response.json()["identity"]["status"] == "READY"
    memberships = (
        await session.scalars(
            select(HouseholdMembership).where(HouseholdMembership.application_user_id == target_id)
        )
    ).all()
    assert {membership.household_id: membership.role for membership in memberships} == {
        first.id: HouseholdRole.ADMIN,
        second.id: HouseholdRole.OWNER,
    }
    mapping = await session.scalar(
        select(LegacyIdentityMapping).where(LegacyIdentityMapping.legacy_identity_id == identity.id)
    )
    assert mapping is not None
    assert mapping.mapped_by_application_user_id == uuid.UUID(administrator["account"]["id"])
    assert (
        await session.scalar(
            select(func.count(HouseholdMembership.id)).where(
                HouseholdMembership.application_user_id == uuid.UUID(administrator["account"]["id"])
            )
        )
        == 0
    )

    duplicate = await client.post(
        f"/api/v1/admin/legacy-identities/{identity.id}/mapping",
        headers={"X-CSRF-Token": client.cookies["hfp_csrf"]},
        json={"application_user_id": str(target_id)},
    )
    assert duplicate.status_code == 409
    listed = await client.get("/api/v1/admin/legacy-identities")
    assert listed.json()["unresolved_count"] == 0
    assert listed.json()["cutover_ready"] is True


async def test_mapping_can_create_a_non_admin_local_account(
    client: AsyncClient, session: AsyncSession
) -> None:
    configure(local_settings())
    await bootstrap(client)
    identity, _, _ = await legacy_households(session)

    response = await client.post(
        f"/api/v1/admin/legacy-identities/{identity.id}/mapping",
        headers={"X-CSRF-Token": client.cookies["hfp_csrf"]},
        json={"new_account": {"username": " Replacement User "}},
    )

    assert response.status_code == 201
    temporary_password = response.json()["temporary_password"]
    mapped = response.json()["identity"]["mapping"]
    assert mapped["username"] == "replacement user"
    account = await session.get(ApplicationUser, uuid.UUID(mapped["application_user_id"]))
    assert account is not None
    assert account.global_role == GlobalRole.USER
    assert account.must_change_password is True
    assert account.password_hash is not None
    assert verify_password(account.password_hash, temporary_password)
    assert account.display_name == "Legacy Person"
    assert account.email == "legacy@example.invalid"
    listed = await client.get("/api/v1/admin/legacy-identities")
    assert listed.json()["activation_pending_count"] == 1
    assert listed.json()["unresolved_count"] == 1
    assert listed.json()["cutover_ready"] is False


async def test_expired_target_credentials_remain_a_cutover_blocker(
    client: AsyncClient, session: AsyncSession
) -> None:
    configure(local_settings())
    await bootstrap(client)
    identity, _, _ = await legacy_households(session)
    target = ApplicationUser(
        username="expired-target",
        password_hash="stored-hash",
        must_change_password=False,
        password_expires_at=utc_now() - timedelta(minutes=1),
    )
    session.add(target)
    await session.commit()

    mapped = await client.post(
        f"/api/v1/admin/legacy-identities/{identity.id}/mapping",
        headers={"X-CSRF-Token": client.cookies["hfp_csrf"]},
        json={"application_user_id": str(target.id)},
    )
    assert mapped.status_code == 201
    assert mapped.json()["identity"]["status"] == "ACTIVATION_PENDING"
    listed = await client.get("/api/v1/admin/legacy-identities")
    assert listed.json()["activation_pending_count"] == 1
    assert listed.json()["cutover_ready"] is False


async def test_reconciliation_applies_role_reduction_removal_and_new_membership(
    client: AsyncClient, session: AsyncSession
) -> None:
    configure(local_settings())
    await bootstrap(client)
    identity, _, second = await legacy_households(session)
    source_id = identity.source_application_user_id
    target = ApplicationUser(
        username="reconciled-target",
        password_hash="stored-hash",
        must_change_password=False,
    )
    session.add(target)
    await session.commit()
    mapped = await client.post(
        f"/api/v1/admin/legacy-identities/{identity.id}/mapping",
        headers={"X-CSRF-Token": client.cookies["hfp_csrf"]},
        json={"application_user_id": str(target.id)},
    )
    assert mapped.status_code == 201

    source_second = await session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.application_user_id == source_id,
            HouseholdMembership.household_id == second.id,
        )
    )
    assert source_second is not None
    source_second.role = HouseholdRole.VIEWER
    third = Household(display_name="New Home", currency="EUR", jurisdiction="DE")
    session.add(third)
    await session.flush()
    session.add(
        HouseholdMembership(
            household_id=third.id,
            application_user_id=source_id,
            role=HouseholdRole.EDITOR,
        )
    )
    await session.commit()

    reconciled = await client.post(
        "/api/v1/admin/legacy-identities/reconcile",
        headers={"X-CSRF-Token": client.cookies["hfp_csrf"]},
    )
    assert reconciled.status_code == 200
    target_roles = {
        membership.household_id: membership.role
        for membership in await session.scalars(
            select(HouseholdMembership).where(HouseholdMembership.application_user_id == target.id)
        )
    }
    assert target_roles[second.id] == HouseholdRole.VIEWER
    assert target_roles[third.id] == HouseholdRole.EDITOR

    await session.delete(source_second)
    await session.commit()
    await client.post(
        "/api/v1/admin/legacy-identities/reconcile",
        headers={"X-CSRF-Token": client.cookies["hfp_csrf"]},
    )
    target_households = set(
        await session.scalars(
            select(HouseholdMembership.household_id).where(
                HouseholdMembership.application_user_id == target.id
            )
        )
    )
    assert second.id not in target_households
    assert third.id in target_households


async def test_mapping_can_be_revoked_audited_and_replaced(
    client: AsyncClient, session: AsyncSession
) -> None:
    configure(local_settings())
    await bootstrap(client)
    identity, first, second = await legacy_households(session)
    first_target = ApplicationUser(
        username="mistaken-target", password_hash="stored-hash", must_change_password=False
    )
    second_target = ApplicationUser(
        username="correct-target", password_hash="stored-hash", must_change_password=False
    )
    session.add_all([first_target, second_target])
    await session.commit()
    headers = {"X-CSRF-Token": client.cookies["hfp_csrf"]}
    mapped = await client.post(
        f"/api/v1/admin/legacy-identities/{identity.id}/mapping",
        headers=headers,
        json={"application_user_id": str(first_target.id)},
    )
    assert mapped.status_code == 201

    revoked = await client.delete(
        f"/api/v1/admin/legacy-identities/{identity.id}/mapping", headers=headers
    )
    assert revoked.status_code == 204
    assert not (
        await session.scalars(
            select(HouseholdMembership).where(
                HouseholdMembership.application_user_id == first_target.id
            )
        )
    ).all()
    replacement = await client.post(
        f"/api/v1/admin/legacy-identities/{identity.id}/mapping",
        headers=headers,
        json={"application_user_id": str(second_target.id)},
    )
    assert replacement.status_code == 201
    replacement_households = set(
        await session.scalars(
            select(HouseholdMembership.household_id).where(
                HouseholdMembership.application_user_id == second_target.id
            )
        )
    )
    assert replacement_households == {first.id, second.id}
    history = await client.get(f"/api/v1/admin/legacy-identities/{identity.id}/mapping-history")
    assert history.status_code == 200
    assert len(history.json()["mappings"]) == 2
    assert history.json()["mappings"][0]["revoked_at"] is not None
    assert history.json()["mappings"][1]["revoked_at"] is None


async def test_mapping_rejects_invalid_or_disabled_targets(
    client: AsyncClient, session: AsyncSession
) -> None:
    configure(local_settings())
    await bootstrap(client)
    identity, _, _ = await legacy_households(session)
    disabled = ApplicationUser(
        username="disabled-user",
        password_hash="not-used",
        is_active=False,
    )
    session.add(disabled)
    await session.commit()

    missing_choice = await client.post(
        f"/api/v1/admin/legacy-identities/{identity.id}/mapping",
        headers={"X-CSRF-Token": client.cookies["hfp_csrf"]},
        json={},
    )
    disabled_choice = await client.post(
        f"/api/v1/admin/legacy-identities/{identity.id}/mapping",
        headers={"X-CSRF-Token": client.cookies["hfp_csrf"]},
        json={"application_user_id": str(disabled.id)},
    )
    assert missing_choice.status_code == 422
    assert disabled_choice.status_code == 409
