"""Opt-in fictional demo-data tests."""

import httpx

from scripts.create_demo_data import DEMO_HOUSEHOLD_NAME, seed_demo


def test_demo_data_is_fictional_explicit_and_idempotent() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.method == "GET":
            return httpx.Response(200, json=[])
        if request.url.path == "/api/v1/households":
            return httpx.Response(
                201,
                json={
                    "id": "demo-household-id",
                    "display_name": DEMO_HOUSEHOLD_NAME,
                    "currency": "AUD",
                    "jurisdiction": "AU",
                },
            )
        return httpx.Response(201, json={"id": "created-id"})

    with httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="http://test",
    ) as client:
        result = seed_demo(client)

    assert result["created"] is True
    assert result["household"]["display_name"] == DEMO_HOUSEHOLD_NAME
    assert [request.method for request in requests] == ["GET", "POST", "POST", "POST", "POST"]


def test_demo_data_reuses_an_existing_named_household() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json=[
                {
                    "id": "existing-id",
                    "display_name": DEMO_HOUSEHOLD_NAME,
                    "currency": "AUD",
                    "jurisdiction": "AU",
                }
            ],
        )

    with httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="http://test",
    ) as client:
        result = seed_demo(client)

    assert result == {
        "household": {
            "id": "existing-id",
            "display_name": DEMO_HOUSEHOLD_NAME,
            "currency": "AUD",
            "jurisdiction": "AU",
        },
        "created": False,
    }
