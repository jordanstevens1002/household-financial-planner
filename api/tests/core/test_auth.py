"""Authentication tests."""

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.core.auth import get_identity
from app.core.config import Settings


async def test_development_identity_is_disabled_by_default() -> None:
    settings = Settings(allow_development_auth=False)
    with pytest.raises(HTTPException) as error:
        await get_identity(_request(), None, "local-user", settings, None)  # type: ignore[arg-type]
    assert error.value.status_code == 401


async def test_development_identity_requires_explicit_opt_in() -> None:
    settings = Settings(allow_development_auth=True)
    identity = await get_identity(
        _request(),
        None,
        "local-user",
        settings,
        None,  # type: ignore[arg-type]
    )
    assert identity.subject == "local-user"


def _request() -> Request:
    return Request({"type": "http", "method": "GET", "path": "/", "headers": []})
