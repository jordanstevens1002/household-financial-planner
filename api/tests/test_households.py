from datetime import date
from uuid import UUID

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import HouseholdMembership, HouseholdRole


async def create_household(client: AsyncClient, name: str = "My household") -> dict[str, str]:
    response = await client.post(
        "/api/v1/households",
        json={"display_name": name, "currency": "AUD", "jurisdiction": "AU"},
    )
    assert response.status_code == 201
    return response.json()


async def test_first_authenticated_request_provisions_user(client: AsyncClient) -> None:
    response = await client.get("/api/v1/me")
    assert response.status_code == 200
    assert response.json()["oidc_subject"] == "test-user"


async def test_household_currency_is_explicit(client: AsyncClient) -> None:
    response = await client.post("/api/v1/households", json={"display_name": "No assumed currency"})
    assert response.status_code == 422


async def test_household_creator_is_owner_and_can_add_person(client: AsyncClient) -> None:
    household = await create_household(client)
    memberships = await client.get(f"/api/v1/households/{household['id']}/memberships")
    assert memberships.status_code == 200
    assert memberships.json()[0]["role"] == "OWNER"

    person = await client.post(
        f"/api/v1/households/{household['id']}/people",
        json={"display_name": "Household member", "effective_from": date.today().isoformat()},
    )
    assert person.status_code == 201
    assert person.json()["household_id"] == household["id"]


async def test_unknown_household_is_hidden(client: AsyncClient) -> None:
    response = await client.get("/api/v1/households/00000000-0000-0000-0000-000000000001")
    assert response.status_code == 404


async def test_person_rejects_invalid_effective_dates(client: AsyncClient) -> None:
    household = await create_household(client)
    response = await client.post(
        f"/api/v1/households/{household['id']}/people",
        json={
            "display_name": "Historical member",
            "effective_from": "2025-01-01",
            "effective_to": "2024-12-31",
        },
    )
    assert response.status_code == 422


async def test_viewer_cannot_add_person(client: AsyncClient, session: AsyncSession) -> None:
    household = await create_household(client)
    membership = await session.scalar(
        select(HouseholdMembership).where(HouseholdMembership.household_id == UUID(household["id"]))
    )
    assert membership is not None
    membership.role = HouseholdRole.VIEWER
    await session.commit()

    response = await client.post(
        f"/api/v1/households/{household['id']}/people",
        json={"display_name": "Blocked member", "effective_from": "2025-01-01"},
    )
    assert response.status_code == 403
