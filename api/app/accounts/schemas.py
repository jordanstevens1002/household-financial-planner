"""Local authentication API contracts."""

import uuid

from pydantic import BaseModel, Field

from app.models import GlobalRole


class Credentials(BaseModel):
    username: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=6, max_length=1024)


class BootstrapRequest(Credentials):
    display_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=1024)
    new_password: str = Field(min_length=6, max_length=1024)


class AccountResponse(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str | None
    email: str | None
    global_role: GlobalRole
    must_change_password: bool


class SessionResponse(BaseModel):
    account: AccountResponse
    csrf_token: str | None = None


class BootstrapStatusResponse(BaseModel):
    bootstrap_required: bool
