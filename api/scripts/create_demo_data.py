"""Create an explicitly requested fictional household through the public API."""

from __future__ import annotations

import argparse
import os
from typing import Any

import httpx

DEMO_HOUSEHOLD_NAME = "Fictional Harbour Household"


def seed_demo(client: httpx.Client) -> dict[str, Any]:
    households = client.get("/api/v1/households")
    households.raise_for_status()
    existing = next(
        (item for item in households.json() if item["display_name"] == DEMO_HOUSEHOLD_NAME),
        None,
    )
    if existing is not None:
        return {"household": existing, "created": False}

    household_response = client.post(
        "/api/v1/households",
        json={
            "display_name": DEMO_HOUSEHOLD_NAME,
            "currency": "AUD",
            "jurisdiction": "AU",
        },
    )
    household_response.raise_for_status()
    household = household_response.json()
    household_id = household["id"]

    for person in (
        {
            "display_name": "Alex Example",
            "legal_name": None,
            "date_of_birth": "1988-04-12",
            "tax_residency_country": "AU",
            "tax_jurisdiction": "AU",
            "effective_from": "2025-01-01",
        },
        {
            "display_name": "Sam Example",
            "legal_name": None,
            "date_of_birth": "1990-09-03",
            "tax_residency_country": "AU",
            "tax_jurisdiction": "AU",
            "effective_from": "2025-01-01",
        },
    ):
        response = client.post(
            f"/api/v1/households/{household_id}/people",
            json=person,
        )
        response.raise_for_status()

    scenario_response = client.post(
        f"/api/v1/households/{household_id}/scenarios",
        json={
            "display_name": "Fictional lower-income scenario",
            "description": "A fictional starting point for exploring the scenario interface.",
            "template_code": None,
            "base_scenario_id": None,
            "is_active": True,
            "overrides": [],
        },
    )
    scenario_response.raise_for_status()
    return {"household": household, "created": True}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm creation of fictional records in the configured local API.",
    )
    arguments = parser.parse_args()
    if not arguments.confirm:
        parser.error("--confirm is required; demo records are never created implicitly")

    base_url = os.getenv("DEMO_API_URL", "http://api:8000")
    development_subject = os.getenv("DEMO_DEVELOPMENT_SUBJECT", "fictional-demo")
    with httpx.Client(
        base_url=base_url,
        headers={"X-Development-Subject": development_subject},
        timeout=15,
    ) as client:
        result = seed_demo(client)

    action = "Created" if result["created"] else "Reused"
    household = result["household"]
    print(f"{action} {household['display_name']} ({household['id']})")


if __name__ == "__main__":
    main()
