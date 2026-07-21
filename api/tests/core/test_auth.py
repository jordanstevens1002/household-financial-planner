"""Authentication tests."""

import pytest
from fastapi import HTTPException

from app.core.auth import get_identity
from app.core.config import Settings


async def test_development_identity_is_disabled_by_default() -> None:
    settings = Settings(allow_development_auth=False)
    with pytest.raises(HTTPException) as error:
        await get_identity(None, "local-user", settings)
    assert error.value.status_code == 401


async def test_development_identity_requires_explicit_opt_in() -> None:
    settings = Settings(allow_development_auth=True)
    identity = await get_identity(None, "local-user", settings)
    assert identity.subject == "local-user"
