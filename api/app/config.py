from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "Household Financial Planner API"
    database_url: str = (
        "postgresql+asyncpg://household_finance:change-me@postgres/household_finance"
    )
    oidc_issuer: AnyHttpUrl = Field(default=AnyHttpUrl("https://identity.example.com/"))
    oidc_audience: str = "household-financial-planner"
    oidc_jwks_url: AnyHttpUrl = Field(
        default=AnyHttpUrl("https://identity.example.com/.well-known/jwks.json")
    )
    allow_development_auth: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    log_format: Literal["json", "console"] = "json"


@lru_cache
def get_settings() -> Settings:
    return Settings()
