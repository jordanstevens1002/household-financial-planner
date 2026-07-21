"""Configuration tests."""

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_logging_settings_are_parsed_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_FORMAT", "console")
    settings = Settings()
    assert settings.log_level == "DEBUG"
    assert settings.log_format == "console"


def test_invalid_log_level_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(log_level="VERBOSE")  # type: ignore[arg-type]


def test_connection_and_identity_settings_are_required(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("DATABASE_URL", "OIDC_ISSUER", "OIDC_JWKS_URL"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(ValidationError) as error:
        Settings(_env_file=None)  # type: ignore[call-arg]
    missing = {item["loc"][0] for item in error.value.errors()}
    assert missing == {"database_url", "oidc_issuer", "oidc_jwks_url"}
