"""Household membership management integration tests."""

import uuid

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Identity, get_identity
from app.main import app
from app.models import (
    ApplicationUser,
    GlobalRole,
    HouseholdMembership,
    HouseholdRole,
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


async def test_owner_can_demote_an_owner_when_another_owner_remains(
    client: AsyncClient, session: AsyncSession
) -> None:
    household = await create_household(client)
    second_owner = await create_local_user(session, "second-owner")
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
