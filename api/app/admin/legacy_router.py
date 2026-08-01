"""Administrative migration of legacy OIDC identities."""

import uuid
from collections import defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.passwords import hash_password
from app.accounts.sessions import utc_now
from app.accounts.tokens import generate_token
from app.admin.legacy_schemas import (
    LegacyIdentityListResponse,
    LegacyIdentityMappedResponse,
    LegacyIdentityMapRequest,
    LegacyIdentityResponse,
    LegacyMappingSummary,
    LegacyMembershipSummary,
)
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.dependencies import ROLE_LEVEL, require_global_admin
from app.core.logging import get_logger
from app.models import (
    ApplicationUser,
    GlobalRole,
    Household,
    HouseholdMembership,
    LegacyIdentity,
    LegacyIdentityMapping,
)

router = APIRouter(prefix="/api/v1/admin/legacy-identities", tags=["administration"])
logger = get_logger(component="legacy_identity_migration")


async def _identity_responses(database: AsyncSession) -> list[LegacyIdentityResponse]:
    identities = list(
        await database.scalars(select(LegacyIdentity).order_by(LegacyIdentity.captured_at))
    )
    if not identities:
        return []

    source_ids = [identity.source_application_user_id for identity in identities]
    membership_rows = (
        await database.execute(
            select(HouseholdMembership, Household)
            .join(Household, Household.id == HouseholdMembership.household_id)
            .where(HouseholdMembership.application_user_id.in_(source_ids))
            .order_by(Household.display_name)
        )
    ).all()
    memberships_by_user: dict[uuid.UUID, list[LegacyMembershipSummary]] = defaultdict(list)
    for membership, household in membership_rows:
        memberships_by_user[membership.application_user_id].append(
            LegacyMembershipSummary(
                household_id=household.id,
                household_name=household.display_name,
                role=membership.role,
            )
        )

    identity_ids = [identity.id for identity in identities]
    mapping_rows = (
        await database.execute(
            select(LegacyIdentityMapping, ApplicationUser)
            .join(ApplicationUser, ApplicationUser.id == LegacyIdentityMapping.application_user_id)
            .where(LegacyIdentityMapping.legacy_identity_id.in_(identity_ids))
        )
    ).all()
    mappings = {
        mapping.legacy_identity_id: LegacyMappingSummary(
            id=mapping.id,
            application_user_id=user.id,
            username=user.username or "",
            display_name=user.display_name,
            mapped_by_application_user_id=mapping.mapped_by_application_user_id,
            mapped_at=mapping.mapped_at,
        )
        for mapping, user in mapping_rows
    }
    return [
        LegacyIdentityResponse(
            id=identity.id,
            oidc_subject=identity.oidc_subject,
            email=identity.email,
            display_name=identity.display_name,
            captured_at=identity.captured_at,
            memberships=memberships_by_user[identity.source_application_user_id],
            mapping=mappings.get(identity.id),
        )
        for identity in identities
    ]


@router.get("", response_model=LegacyIdentityListResponse)
async def list_legacy_identities(
    _: ApplicationUser = Depends(require_global_admin),
    database: AsyncSession = Depends(get_session),
) -> LegacyIdentityListResponse:
    identities = await _identity_responses(database)
    return LegacyIdentityListResponse(
        identities=identities,
        unresolved_count=sum(identity.mapping is None for identity in identities),
    )


@router.post(
    "/{legacy_identity_id}/mapping",
    response_model=LegacyIdentityMappedResponse,
    status_code=status.HTTP_201_CREATED,
)
async def map_legacy_identity(
    legacy_identity_id: uuid.UUID,
    payload: LegacyIdentityMapRequest,
    actor: ApplicationUser = Depends(require_global_admin),
    database: AsyncSession = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> LegacyIdentityMappedResponse:
    identity = await database.scalar(
        select(LegacyIdentity).where(LegacyIdentity.id == legacy_identity_id).with_for_update()
    )
    if identity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Legacy identity not found")
    existing_mapping = await database.scalar(
        select(LegacyIdentityMapping).where(LegacyIdentityMapping.legacy_identity_id == identity.id)
    )
    if existing_mapping is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Legacy identity is already mapped")

    temporary_password: str | None = None
    if payload.new_account is not None:
        temporary_password = generate_token()
        account = ApplicationUser(
            username=payload.new_account.username,
            password_hash=hash_password(temporary_password),
            display_name=payload.new_account.display_name or identity.display_name,
            email=payload.new_account.email or identity.email,
            global_role=GlobalRole.USER,
            must_change_password=True,
            password_expires_at=utc_now() + timedelta(hours=settings.temp_password_hours),
        )
        database.add(account)
        await database.flush()
    else:
        assert payload.application_user_id is not None
        existing_account = await database.scalar(
            select(ApplicationUser)
            .where(ApplicationUser.id == payload.application_user_id)
            .with_for_update()
        )
        if existing_account is None or existing_account.username is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Local account not found")
        if not existing_account.is_active:
            raise HTTPException(status.HTTP_409_CONFLICT, "Cannot map to a disabled account")
        account = existing_account

    source_memberships = list(
        await database.scalars(
            select(HouseholdMembership)
            .where(HouseholdMembership.application_user_id == identity.source_application_user_id)
            .with_for_update()
        )
    )
    target_memberships = {
        membership.household_id: membership
        for membership in await database.scalars(
            select(HouseholdMembership)
            .where(HouseholdMembership.application_user_id == account.id)
            .with_for_update()
        )
    }
    for source_membership in source_memberships:
        target_membership = target_memberships.get(source_membership.household_id)
        if target_membership is None:
            database.add(
                HouseholdMembership(
                    household_id=source_membership.household_id,
                    application_user_id=account.id,
                    role=source_membership.role,
                )
            )
        elif ROLE_LEVEL[source_membership.role] > ROLE_LEVEL[target_membership.role]:
            target_membership.role = source_membership.role

    mapping = LegacyIdentityMapping(
        legacy_identity_id=identity.id,
        application_user_id=account.id,
        mapped_by_application_user_id=actor.id,
    )
    database.add(mapping)
    try:
        await database.commit()
    except IntegrityError as exc:
        await database.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The identity mapping conflicts with an existing account or mapping",
        ) from exc

    logger.info(
        "legacy_identity_mapped",
        actor_user_id=str(actor.id),
        legacy_identity_id=str(identity.id),
        target_user_id=str(account.id),
        transferred_household_count=len(source_memberships),
    )
    identities = await _identity_responses(database)
    mapped_identity = next(item for item in identities if item.id == identity.id)
    return LegacyIdentityMappedResponse(
        identity=mapped_identity,
        temporary_password=temporary_password,
    )
