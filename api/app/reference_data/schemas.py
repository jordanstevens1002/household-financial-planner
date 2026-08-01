"""Reference-data API schemas."""

from pydantic import BaseModel


class CountryRead(BaseModel):
    code: str
    display_name: str
    flag: str
    recommended_currency: str | None


class CurrencyRead(BaseModel):
    code: str
    display_name: str
    numeric_code: str
