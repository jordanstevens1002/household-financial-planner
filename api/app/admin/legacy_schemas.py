"""Contracts for migrating legacy OIDC identities to local accounts."""

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from app.accounts.usernames import normalise_username
from app.models import HouseholdRole


class LegacyMembershipSummary(BaseModel):
    household_id: uuid.UUID
    household_name: str
    role: HouseholdRole


class LegacyIdentityStatus(StrEnum):
    UNMAPPED = "UNMAPPED"
    ACTIVATION_PENDING = "ACTIVATION_PENDING"
    READY = "READY"


class LegacyMappingSummary(BaseModel):
    id: uuid.UUID
    application_user_id: uuid.UUID
    username: str
    display_name: str | None
    mapped_by_application_user_id: uuid.UUID
    mapped_at: datetime
    last_reconciled_at: datetime | None
    revoked_at: datetime | None = None
    revoked_by_application_user_id: uuid.UUID | None = None


class LegacyIdentityResponse(BaseModel):
    id: uuid.UUID
    oidc_subject: str
    email: str | None
    display_name: str | None
    captured_at: datetime
    memberships: list[LegacyMembershipSummary]
    mapping: LegacyMappingSummary | None
    status: LegacyIdentityStatus


class LegacyMigrationReviewRequest(BaseModel):
    unresolved_identity_ids: list[uuid.UUID]
    accept_login_loss: bool = False


class LegacyMigrationReviewSummary(BaseModel):
    id: uuid.UUID
    reviewed_by_application_user_id: uuid.UUID
    reviewed_at: datetime
    unresolved_identity_ids: list[uuid.UUID]
    accepted_login_loss: bool


class LegacyMigrationReviewHistory(BaseModel):
    reviews: list[LegacyMigrationReviewSummary]


class LegacyIdentityListResponse(BaseModel):
    identities: list[LegacyIdentityResponse]
    unresolved_count: int
    activation_pending_count: int
    cutover_ready: bool
    active_review: LegacyMigrationReviewSummary | None = None


class LegacyLocalAccountCreate(BaseModel):
    username: str = Field(min_length=1, max_length=320)
    display_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=320)

    @model_validator(mode="after")
    def normalise(self) -> LegacyLocalAccountCreate:
        self.username = normalise_username(self.username)
        return self


class LegacyIdentityMapRequest(BaseModel):
    application_user_id: uuid.UUID | None = None
    new_account: LegacyLocalAccountCreate | None = None

    @model_validator(mode="after")
    def select_exactly_one_target(self) -> LegacyIdentityMapRequest:
        if (self.application_user_id is None) == (self.new_account is None):
            raise ValueError("Select either an existing account or a new account")
        return self


class LegacyIdentityMappedResponse(BaseModel):
    identity: LegacyIdentityResponse
    temporary_password: str | None = None


class LegacyMappingHistoryResponse(BaseModel):
    mappings: list[LegacyMappingSummary]
