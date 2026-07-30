"""Authentication boundary."""

from dataclasses import dataclass

import jwt
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.sessions import resolve_session
from app.core.config import Settings, get_settings
from app.core.database import get_session


@dataclass(frozen=True)
class Identity:
    subject: str
    email: str | None = None
    display_name: str | None = None
    application_user_id: str | None = None


bearer = HTTPBearer(auto_error=False)


async def get_identity(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    development_subject: str | None = Header(default=None, alias="X-Development-Subject"),
    settings: Settings = Depends(get_settings),
    session: AsyncSession = Depends(get_session),
) -> Identity:
    local = await resolve_session(request, session, settings)
    if local is not None:
        user, _ = local
        return Identity(
            subject=f"local:{user.id}",
            email=user.email,
            display_name=user.display_name,
            application_user_id=str(user.id),
        )
    if settings.allow_development_auth and development_subject:
        return Identity(subject=development_subject)
    if credentials is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Bearer token required")
    try:
        key_client = jwt.PyJWKClient(str(settings.oidc_jwks_url))
        signing_key = key_client.get_signing_key_from_jwt(credentials.credentials)
        claims = jwt.decode(
            credentials.credentials,
            signing_key.key,
            algorithms=["RS256", "ES256"],
            audience=settings.oidc_audience,
            issuer=str(settings.oidc_issuer),
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid bearer token") from exc
    subject = claims.get("sub")
    if not subject:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token subject missing")
    return Identity(subject=subject, email=claims.get("email"), display_name=claims.get("name"))
