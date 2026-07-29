"""Country and currency reference-data routes."""

from typing import Any

import pycountry
from fastapi import APIRouter, Depends

from app.core.dependencies import current_user
from app.models import ApplicationUser
from app.reference_data.schemas import CountryRead, CurrencyRead

router = APIRouter(prefix="/api/v1/reference", tags=["reference data"])


def _flag(code: str) -> str:
    return "".join(chr(127397 + ord(character)) for character in code)


def countries() -> list[CountryRead]:
    records: list[Any] = list(pycountry.countries)
    return sorted(
        (
            CountryRead(
                code=record.alpha_2,
                display_name=record.name,
                flag=_flag(record.alpha_2),
            )
            for record in records
        ),
        key=lambda item: item.display_name,
    )


def currencies() -> list[CurrencyRead]:
    records: list[Any] = list(pycountry.currencies)
    return sorted(
        (
            CurrencyRead(
                code=record.alpha_3,
                display_name=record.name,
                numeric_code=record.numeric,
            )
            for record in records
            if getattr(record, "numeric", None)
        ),
        key=lambda item: item.code,
    )


@router.get("/countries", response_model=list[CountryRead])
async def list_countries(_: ApplicationUser = Depends(current_user)) -> list[CountryRead]:
    return countries()


@router.get("/currencies", response_model=list[CurrencyRead])
async def list_currencies(_: ApplicationUser = Depends(current_user)) -> list[CurrencyRead]:
    return currencies()
