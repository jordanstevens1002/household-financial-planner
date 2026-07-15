from dataclasses import dataclass

import jwt
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings


@dataclass(frozen=True)
class Identity:
    subject: str
    email: str | None = None
    display_name: str | None = None


bearer = HTTPBearer(auto_error=False)


async def get_identity(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    development_subject: str | None = Header(default=None, alias="X-Development-Subject"),
    settings: Settings = Depends(get_settings),
) -> Identity:
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
