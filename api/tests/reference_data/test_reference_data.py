"""Country and currency reference-data API tests."""

from httpx import AsyncClient


async def test_country_reference_is_sorted_and_includes_flag_labels(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/reference/countries")

    assert response.status_code == 200
    records = response.json()
    assert len(records) >= 240
    assert [item["display_name"] for item in records] == sorted(
        item["display_name"] for item in records
    )
    australia = next(item for item in records if item["code"] == "AU")
    assert australia == {
        "code": "AU",
        "display_name": "Australia",
        "flag": "🇦🇺",
    }
    assert not any(item["code"] == "" for item in records)


async def test_currency_reference_is_sorted_without_a_default(
    client: AsyncClient,
) -> None:
    response = await client.get("/api/v1/reference/currencies")

    assert response.status_code == 200
    records = response.json()
    assert len(records) >= 150
    assert [item["code"] for item in records] == sorted(item["code"] for item in records)
    aud = next(item for item in records if item["code"] == "AUD")
    assert aud["display_name"] == "Australian Dollar"
    assert aud["numeric_code"] == "036"
    assert all(len(item["code"]) == 3 for item in records)
