import pytest
from pydantic import ValidationError

from app.config import Settings


def test_logging_settings_are_parsed_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_FORMAT", "console")
    settings = Settings()
    assert settings.log_level == "DEBUG"
    assert settings.log_format == "console"


def test_invalid_log_level_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(log_level="VERBOSE")  # type: ignore[arg-type]
