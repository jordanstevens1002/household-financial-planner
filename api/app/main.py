import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from time import perf_counter

import structlog
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.requests import Request
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import RequestResponseEndpoint

from app.core.config import get_settings
from app.core.database import get_session
from app.core.logging import configure_logging, get_logger
from app.events.router import router as events_router
from app.households.router import router as households_router
from app.income.router import router as income_router
from app.loans.router import router as loans_router
from app.properties.router import router as properties_router
from app.purchases.router import router as purchases_router
from app.rental.router import router as rental_router
from app.retirement.router import router as retirement_router
from app.scenarios.router import router as scenarios_router

settings = get_settings()
configure_logging(settings)
logger = get_logger(component="api")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    logger.info("application_started", version="0.10.0")
    try:
        yield
    finally:
        logger.info("application_stopped")


app = FastAPI(title="Household Financial Planner API", version="0.10.0", lifespan=lifespan)
app.include_router(households_router)
app.include_router(properties_router)
app.include_router(events_router)
app.include_router(loans_router)
app.include_router(rental_router)
app.include_router(income_router)
app.include_router(retirement_router)
app.include_router(purchases_router)
app.include_router(scenarios_router)


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
