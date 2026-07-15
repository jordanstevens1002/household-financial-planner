from httpx import AsyncClient


async def test_liveness_does_not_require_database(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_checks_database(client: AsyncClient) -> None:
    response = await client.get("/health/ready")
    assert response.status_code == 200
    assert response.json() == {"status": "ready"}


async def test_request_id_is_generated_and_returned(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.headers["X-Request-ID"]


async def test_request_id_is_preserved(client: AsyncClient) -> None:
    response = await client.get("/health/live", headers={"X-Request-ID": "manual-test-id"})
    assert response.headers["X-Request-ID"] == "manual-test-id"
