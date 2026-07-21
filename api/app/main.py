import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter
from typing import Annotated

import structlog
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.requests import Request
from fastapi.responses import Response
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import RequestResponseEndpoint

from app.config import get_settings
from app.database import get_session
from app.dependencies import current_user, require_household_role
from app.events import router as events_router
from app.income import router as income_router
from app.loans import router as loans_router
from app.logging import configure_logging, get_logger
from app.models import (
    ApplicationUser,
    Household,
    HouseholdMembership,
    HouseholdRole,
    LookupItem,
    Person,
)
from app.properties import router as properties_router
from app.rental import router as rental_router
from app.retirement import router as retirement_router
from app.schemas import (
    HouseholdCreate,
    HouseholdRead,
    LookupRead,
    MembershipRead,
    PersonCreate,
    PersonRead,
    UserRead,
)

settings = get_settings()
configure_logging(settings)
logger = get_logger(component="api")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("application_started", version="0.7.0")
    try:
        yield
    finally:
        logger.info("application_stopped")


app = FastAPI(title="Household Financial Planner API", version="0.7.0", lifespan=lifespan)
app.include_router(properties_router)
app.include_router(events_router)
app.include_router(loans_router)
app.include_router(rental_router)
app.include_router(income_router)
app.include_router(retirement_router)


@app.middleware("http")
async def log_request(request: Request, call_next: RequestResponseEndpoint) -> Response:
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(
        request_id=request_id,
        http_method=request.method,
        http_path=request.url.path,
    )
    started_at = perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception(
            "request_failed",
            duration_ms=round((perf_counter() - started_at) * 1000, 2),
        )
        raise
    else:
        logger.info(
            "request_completed",
            status_code=response.status_code,
            duration_ms=round((perf_counter() - started_at) * 1000, 2),
        )
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        structlog.contextvars.clear_contextvars()


@app.get("/health/live", tags=["health"])
async def live() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
async def ready(session: AsyncSession = Depends(get_session)) -> dict[str, str]:
    try:
        await session.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable") from exc
    return {"status": "ready"}


@app.get("/api/v1/me", response_model=UserRead)
async def me(user: ApplicationUser = Depends(current_user)) -> ApplicationUser:
    return user


@app.get("/api/v1/households", response_model=list[HouseholdRead])
async def list_households(
    user: ApplicationUser = Depends(current_user), session: AsyncSession = Depends(get_session)
) -> list[Household]:
    result = await session.scalars(
        select(Household)
        .join(HouseholdMembership)
        .where(HouseholdMembership.application_user_id == user.id)
    )
    return list(result)


@app.post("/api/v1/households", response_model=HouseholdRead, status_code=201)
async def create_household(
    payload: HouseholdCreate,
    user: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> Household:
    household = Household(**payload.model_dump())
    session.add(household)
    await session.flush()
    session.add(
        HouseholdMembership(
            household_id=household.id, application_user_id=user.id, role=HouseholdRole.OWNER
        )
    )
    await session.commit()
    await session.refresh(household)
    return household


@app.get("/api/v1/households/{household_id}", response_model=HouseholdRead)
async def get_household(
    household_id: uuid.UUID,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.VIEWER))],
    session: AsyncSession = Depends(get_session),
) -> Household:
    household = await session.get(Household, household_id)
    if household is None:
        raise HTTPException(404, "Household not found")
    return household


@app.get("/api/v1/households/{household_id}/memberships", response_model=list[MembershipRead])
async def list_memberships(
    household_id: uuid.UUID,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.ADMIN))],
    session: AsyncSession = Depends(get_session),
) -> list[HouseholdMembership]:
    return list(
        await session.scalars(
            select(HouseholdMembership).where(HouseholdMembership.household_id == household_id)
        )
    )


@app.get("/api/v1/households/{household_id}/people", response_model=list[PersonRead])
async def list_people(
    household_id: uuid.UUID,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.VIEWER))],
    session: AsyncSession = Depends(get_session),
) -> list[Person]:
    return list(await session.scalars(select(Person).where(Person.household_id == household_id)))


@app.post("/api/v1/households/{household_id}/people", response_model=PersonRead, status_code=201)
async def create_person(
    household_id: uuid.UUID,
    payload: PersonCreate,
    _: Annotated[HouseholdMembership, Depends(require_household_role(HouseholdRole.EDITOR))],
    session: AsyncSession = Depends(get_session),
) -> Person:
    person = Person(household_id=household_id, **payload.model_dump())
    session.add(person)
    await session.commit()
    await session.refresh(person)
    return person


@app.get("/api/v1/lookups/{category}", response_model=list[LookupRead])
async def list_lookups(
    category: str,
    active_only: bool = Query(default=True),
    _: ApplicationUser = Depends(current_user),
    session: AsyncSession = Depends(get_session),
) -> list[LookupItem]:
    query = select(LookupItem).where(LookupItem.category == category)
    if active_only:
        query = query.where(LookupItem.is_active.is_(True))
    return list(await session.scalars(query.order_by(LookupItem.display_name)))
