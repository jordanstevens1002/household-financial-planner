"""Household membership management integration tests."""

import logging
import uuid
from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.sessions import utc_now
from app.admin.legacy_memberships import reconcile_mapping, revoke_mapping_memberships
from app.core.auth import Identity, get_identity
from app.main import app
from app.models import (
    ApplicationUser,
    GlobalRole,
    HouseholdMembership,
    HouseholdRole,
    LegacyIdentity,
    LegacyIdentityMapping,
    LegacyMembershipBaseline,
    LegacyMembershipGrant,
)


async def create_household(client: AsyncClient) -> dict:
    response = await client.post(
        "/api/v1/households",
        json={"display_name": "Shared home", "currency": "NZD", "jurisdiction": "NZ"},
    )
    assert response.status_code == 201
    return response.json()


async def create_local_user(
    session: AsyncSession,
    username: str,
    *,
    is_active: bool = True,
    global_role: GlobalRole = GlobalRole.USER,
) -> ApplicationUser:
    user = ApplicationUser(
        username=username,
        display_name=username.replace("-", " ").title(),
        email=f"{username}@example.test",
        global_role=global_role,
        is_active=is_active,
        must_change_password=False,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


def act_as(user: ApplicationUser) -> None:
    async def identity_override() -> Identity:
        return Identity(subject=f"local:{user.id}", application_user_id=str(user.id))

    app.dependency_overrides[get_identity] = identity_override


async def membership_for(
    session: AsyncSession, household_id: str, user_id: uuid.UUID
) -> HouseholdMembership:
    membership = await session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == uuid.UUID(household_id),
            HouseholdMembership.application_user_id == user_id,
        )
    )
    assert membership is not None
    return membership


async def test_owner_adds_local_member_and_response_excludes_sensitive_account_data(
    client: AsyncClient, session: AsyncSession
) -> None:
    household = await create_household(client)
    member = await create_local_user(session, "new-member")

    response = await client.post(
        f"/api/v1/households/{household['id']}/memberships",
        json={"username": "  NEW-MEMBER ", "role": "EDITOR"},
    )

    assert response.status_code == 201
    assert response.json() == {
        "id": response.json()["id"],
        "household_id": household["id"],
        "application_user_id": str(member.id),
        "role": "EDITOR",
        "username": "new-member",
        "display_name": "New Member",
        "is_active": True,
    }
    for sensitive_field in ("email", "global_role", "password_hash", "oidc_subject"):
        assert sensitive_field not in response.text
    listed = await client.get(f"/api/v1/households/{household['id']}/memberships")
    assert listed.status_code == 200
    listed_member = next(item for item in listed.json() if item["username"] == "new-member")
    assert listed_member == response.json()


async def test_administrator_manages_roles_up_to_administrator(
    client: AsyncClient, session: AsyncSession
) -> None:
    household = await create_household(client)
    administrator = await create_local_user(session, "household-admin")
    editor = await create_local_user(session, "household-editor")
    session.add(
        HouseholdMembership(
            household_id=uuid.UUID(household["id"]),
            application_user_id=administrator.id,
            role=HouseholdRole.ADMIN,
        )
    )
    await session.commit()
    act_as(administrator)

    created = await client.post(
        f"/api/v1/households/{household['id']}/memberships",
        json={"username": editor.username, "role": "EDITOR"},
    )
    assert created.status_code == 201
    membership_id = created.json()["id"]
    updated = await client.patch(
        f"/api/v1/households/{household['id']}/memberships/{membership_id}",
        json={"role": "ADMIN"},
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "ADMIN"
    deleted = await client.delete(
        f"/api/v1/households/{household['id']}/memberships/{membership_id}"
    )
    assert deleted.status_code == 204


async def test_administrator_cannot_create_change_or_remove_owner(
    client: AsyncClient, session: AsyncSession
) -> None:
    household = await create_household(client)
    owner_membership = await session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == uuid.UUID(household["id"])
        )
    )
    assert owner_membership is not None
    administrator = await create_local_user(session, "household-admin")
    candidate = await create_local_user(session, "owner-candidate")
    session.add(
        HouseholdMembership(
            household_id=uuid.UUID(household["id"]),
            application_user_id=administrator.id,
            role=HouseholdRole.ADMIN,
        )
    )
    await session.commit()
    act_as(administrator)

    create_owner = await client.post(
        f"/api/v1/households/{household['id']}/memberships",
        json={"username": candidate.username, "role": "OWNER"},
    )
    change_owner = await client.patch(
        f"/api/v1/households/{household['id']}/memberships/{owner_membership.id}",
        json={"role": "ADMIN"},
    )
    remove_owner = await client.delete(
        f"/api/v1/households/{household['id']}/memberships/{owner_membership.id}"
    )
    assert [create_owner.status_code, change_owner.status_code, remove_owner.status_code] == [
        403,
        403,
        403,
    ]


async def test_final_owner_cannot_be_demoted_or_removed(
    client: AsyncClient, session: AsyncSession
) -> None:
    household = await create_household(client)
    owner = await session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == uuid.UUID(household["id"])
        )
    )
    assert owner is not None

    demoted = await client.patch(
        f"/api/v1/households/{household['id']}/memberships/{owner.id}",
        json={"role": "ADMIN"},
    )
    removed = await client.delete(f"/api/v1/households/{household['id']}/memberships/{owner.id}")
    assert demoted.status_code == 409
    assert removed.status_code == 409


async def test_disabled_and_expired_local_owners_do_not_satisfy_final_owner_guard(
    client: AsyncClient, session: AsyncSession
) -> None:
    for suffix, user_kwargs in (
        ("disabled", {"is_active": False}),
        ("expired", {}),
    ):
        household = await create_household(client)
        local_owner = await create_local_user(session, f"{suffix}-owner", **user_kwargs)
        local_owner.password_hash = "stored-hash"
        local_owner.must_change_password = False
        if suffix == "expired":
            local_owner.password_expires_at = utc_now() - timedelta(minutes=1)
        session.add(
            HouseholdMembership(
                household_id=uuid.UUID(household["id"]),
                application_user_id=local_owner.id,
                role=HouseholdRole.OWNER,
            )
        )
        await session.commit()
        accessible_owner = await session.scalar(
            select(HouseholdMembership).where(
                HouseholdMembership.household_id == uuid.UUID(household["id"]),
                HouseholdMembership.application_user_id != local_owner.id,
            )
        )
        assert accessible_owner is not None

        demoted = await client.patch(
            f"/api/v1/households/{household['id']}/memberships/{accessible_owner.id}",
            json={"role": "ADMIN"},
        )
        removed = await client.delete(
            f"/api/v1/households/{household['id']}/memberships/{accessible_owner.id}"
        )
        assert demoted.status_code == 409
        assert removed.status_code == 409


async def test_owner_can_demote_an_owner_when_another_owner_remains(
    client: AsyncClient, session: AsyncSession
) -> None:
    household = await create_household(client)
    second_owner = await create_local_user(session, "second-owner")
    second_owner.password_hash = "stored-hash"
    second_owner.must_change_password = False
    await session.commit()
    added = await client.post(
        f"/api/v1/households/{household['id']}/memberships",
        json={"username": second_owner.username, "role": "OWNER"},
    )
    assert added.status_code == 201

    demoted = await client.patch(
        f"/api/v1/households/{household['id']}/memberships/{added.json()['id']}",
        json={"role": "VIEWER"},
    )
    assert demoted.status_code == 200
    assert demoted.json()["role"] == "VIEWER"


async def test_global_administrator_has_no_implicit_household_access(
    client: AsyncClient, session: AsyncSession
) -> None:
    household = await create_household(client)
    global_admin = await create_local_user(session, "global-admin", global_role=GlobalRole.ADMIN)
    act_as(global_admin)

    response = await client.get(f"/api/v1/households/{household['id']}/memberships")

    assert response.status_code == 404


async def test_membership_mutations_are_isolated_to_the_requested_household(
    client: AsyncClient, session: AsyncSession
) -> None:
    first = await create_household(client)
    second = await create_household(client)
    member = await create_local_user(session, "isolated-member")
    added = await client.post(
        f"/api/v1/households/{first['id']}/memberships",
        json={"username": member.username, "role": "VIEWER"},
    )
    assert added.status_code == 201

    wrong_household = await client.patch(
        f"/api/v1/households/{second['id']}/memberships/{added.json()['id']}",
        json={"role": "EDITOR"},
    )
    assert wrong_household.status_code == 404
    membership = await membership_for(session, first["id"], member.id)
    assert membership.role == HouseholdRole.VIEWER


async def test_unknown_inactive_and_duplicate_accounts_are_not_added(
    client: AsyncClient, session: AsyncSession
) -> None:
    household = await create_household(client)
    inactive = await create_local_user(session, "inactive-member", is_active=False)
    for username in ("missing-member", inactive.username):
        response = await client.post(
            f"/api/v1/households/{household['id']}/memberships",
            json={"username": username, "role": "VIEWER"},
        )
        assert response.status_code == 404

    active = await create_local_user(session, "active-member")
    first = await client.post(
        f"/api/v1/households/{household['id']}/memberships",
        json={"username": active.username, "role": "VIEWER"},
    )
    duplicate = await client.post(
        f"/api/v1/households/{household['id']}/memberships",
        json={"username": active.username, "role": "EDITOR"},
    )
    assert first.status_code == 201
    assert duplicate.status_code == 409


async def test_inherited_membership_rejects_direct_changes_and_revocation_preserves_baseline(
    client: AsyncClient, session: AsyncSession
) -> None:
    household = await create_household(client)
    actor_membership = await session.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.household_id == uuid.UUID(household["id"])
        )
    )
    assert actor_membership is not None
    source = ApplicationUser(oidc_subject="legacy-membership-source", is_active=True)
    target = await create_local_user(session, "mapped-member")
    target.password_hash = "stored-hash"
    session.add(source)
    await session.flush()
    source_membership = HouseholdMembership(
        household_id=uuid.UUID(household["id"]),
        application_user_id=source.id,
        role=HouseholdRole.OWNER,
    )
    session.add(source_membership)
    identity = LegacyIdentity(
        source_application_user_id=source.id,
        oidc_subject=source.oidc_subject,
    )
    session.add(identity)
    await session.flush()
    mapping = LegacyIdentityMapping(
        legacy_identity_id=identity.id,
        application_user_id=target.id,
        mapped_by_application_user_id=actor_membership.application_user_id,
    )
    session.add(mapping)
    await session.flush()
    baseline = LegacyMembershipBaseline(
        application_user_id=target.id,
        household_id=uuid.UUID(household["id"]),
        original_role=HouseholdRole.EDITOR,
    )
    grant = LegacyMembershipGrant(
        legacy_identity_mapping_id=mapping.id,
        household_id=uuid.UUID(household["id"]),
        role=HouseholdRole.OWNER,
    )
    inherited = HouseholdMembership(
        household_id=uuid.UUID(household["id"]),
        application_user_id=target.id,
        role=HouseholdRole.OWNER,
    )
    session.add_all([baseline, grant, inherited])
    await session.commit()

    updated = await client.patch(
        f"/api/v1/households/{household['id']}/memberships/{inherited.id}",
        json={"role": "VIEWER"},
    )
    deleted = await client.delete(
        f"/api/v1/households/{household['id']}/memberships/{inherited.id}"
    )
    assert updated.status_code == 409
    assert deleted.status_code == 409
    assert "legacy identity" in updated.json()["detail"]

    source_membership.role = HouseholdRole.VIEWER
    await reconcile_mapping(session, mapping)
    await session.commit()
    await session.refresh(inherited)
    assert inherited.role == HouseholdRole.EDITOR

    await revoke_mapping_memberships(session, mapping)
    await session.commit()
    await session.refresh(inherited)
    assert inherited.role == HouseholdRole.EDITOR


async def test_direct_membership_mutations_update_legacy_baseline_and_emit_audit_logs(
    client: AsyncClient, session: AsyncSession, caplog
) -> None:
    household = await create_household(client)
    member = await create_local_user(session, "audited-household-member")
    baseline = LegacyMembershipBaseline(
        application_user_id=member.id,
        household_id=uuid.UUID(household["id"]),
        original_role=None,
    )
    session.add(baseline)
    await session.commit()

    with caplog.at_level(logging.INFO):
        created = await client.post(
            f"/api/v1/households/{household['id']}/memberships",
            json={"username": member.username, "role": "VIEWER"},
        )
        updated = await client.patch(
            f"/api/v1/households/{household['id']}/memberships/{created.json()['id']}",
            json={"role": "EDITOR"},
        )
        deleted = await client.delete(
            f"/api/v1/households/{household['id']}/memberships/{created.json()['id']}"
        )
    assert [created.status_code, updated.status_code, deleted.status_code] == [201, 200, 204]
    await session.refresh(baseline)
    assert baseline.original_role is None
    assert "household_membership_created" in caplog.text
    assert "household_membership_updated" in caplog.text
    assert "household_membership_deleted" in caplog.text
    assert str(member.id) in caplog.text
    assert household["id"] in caplog.text
    assert "previous_role" in caplog.text
    assert "resulting_role" in caplog.text
