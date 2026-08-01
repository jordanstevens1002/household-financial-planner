"""Authenticated installation diagnostics."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.dependencies import current_user
from app.core.version import APPLICATION_VERSION
from app.models import ApplicationUser

router = APIRouter(prefix="/api/v1/system", tags=["system"])


class SystemStatusRead(BaseModel):
    status: Literal["ready"]
    version: str


@router.get("/status", response_model=SystemStatusRead)
async def system_status(
    _: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> SystemStatusRead:
    """Check database readiness for an authenticated application user."""
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable") from exc
    return SystemStatusRead(status="ready", version=APPLICATION_VERSION)
