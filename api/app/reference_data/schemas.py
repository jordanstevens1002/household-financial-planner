"""Reference-data API schemas."""

from pydantic import BaseModel


class CountryRead(BaseModel):
    code: str
    display_name: str
    flag: str


class CurrencyRead(BaseModel):
    code: str
    display_name: str
    numeric_code: str
