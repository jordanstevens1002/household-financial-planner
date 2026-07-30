"""Global account administration API contracts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from app.accounts.usernames import normalise_username
from app.models import GlobalRole


class AdminUserResponse(BaseModel):
    id: uuid.UUID
    username: str
    display_name: str | None
    email: str | None
    global_role: GlobalRole
    is_active: bool
    must_change_password: bool
    password_expires_at: datetime | None
    created_at: datetime


class AdminUserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=320)
    display_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    global_role: GlobalRole = GlobalRole.USER

    @model_validator(mode="after")
    def normalise(self) -> AdminUserCreate:
        self.username = normalise_username(self.username)
        return self


class AdminUserCreated(BaseModel):
    account: AdminUserResponse
    temporary_password: str


class AdminUserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=320)
    display_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    global_role: GlobalRole | None = None
    is_active: bool | None = None
    confirm_self_lockout: bool = False

    @model_validator(mode="after")
    def validate_update(self) -> AdminUserUpdate:
        mutable_fields = self.model_fields_set - {"confirm_self_lockout"}
        if not mutable_fields:
            raise ValueError("At least one field must be supplied")
        for required_field in ("username", "global_role", "is_active"):
            if required_field in self.model_fields_set and getattr(self, required_field) is None:
                raise ValueError(f"{required_field} cannot be null")
        if self.username is not None:
            self.username = normalise_username(self.username)
        return self


class PasswordResetIssued(BaseModel):
    reset_path: str
    expires_at: datetime
