"""Health and application metadata tests."""

from importlib.metadata import version

from httpx import AsyncClient

from app.core.version import APPLICATION_VERSION
from app.main import app


def test_api_reports_release_version() -> None:
    package_version = version("household-financial-planner-api")
    assert APPLICATION_VERSION == package_version
    assert app.version == package_version


async def test_liveness_does_not_require_database(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": APPLICATION_VERSION}


async def test_authenticated_system_status_checks_database(client: AsyncClient) -> None:
    response = await client.get("/api/v1/system/status")
    assert response.status_code == 200
    assert response.json() == {"status": "ready", "version": APPLICATION_VERSION}


async def test_database_readiness_is_not_publicly_routable(client: AsyncClient) -> None:
    for _ in range(3):
        response = await client.get("/health/ready")
        assert response.status_code == 404


async def test_request_id_is_generated_and_returned(client: AsyncClient) -> None:
    response = await client.get("/health/live")
    assert response.headers["X-Request-ID"]


async def test_request_id_is_preserved(client: AsyncClient) -> None:
    response = await client.get("/health/live", headers={"X-Request-ID": "manual-test-id"})
    assert response.headers["X-Request-ID"] == "manual-test-id"
