"""Typed application configuration."""

from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Household Financial Planner API"
    database_url: str
    oidc_issuer: AnyHttpUrl
    oidc_audience: str = "household-financial-planner"
    oidc_jwks_url: AnyHttpUrl
    allow_development_auth: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "console"] = "json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
