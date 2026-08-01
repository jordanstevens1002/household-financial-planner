"""Administrative migration of legacy OIDC identities."""

import hashlib
import json
import uuid
from collections import defaultdict
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.passwords import hash_password
from app.accounts.sessions import as_utc, utc_now
from app.accounts.tokens import generate_token
from app.admin.legacy_memberships import reconcile_mapping, revoke_mapping_memberships
from app.admin.legacy_schemas import (
    LegacyIdentityListResponse,
    LegacyIdentityMappedResponse,
    LegacyIdentityMapRequest,
    LegacyIdentityResponse,
    LegacyIdentityStatus,
    LegacyMappingHistoryResponse,
    LegacyMappingSummary,
    LegacyMembershipSummary,
    LegacyMigrationReviewHistory,
    LegacyMigrationReviewRequest,
    LegacyMigrationReviewSummary,
)
from app.core.config import Settings, get_settings
from app.core.database import get_session
from app.core.dependencies import require_global_admin
from app.core.logging import get_logger
from app.models import (
    ApplicationUser,
    GlobalRole,
    Household,
    HouseholdMembership,
    LegacyIdentity,
    LegacyIdentityMapping,
    LegacyMigrationReview,
)

router = APIRouter(prefix="/api/v1/admin/legacy-identities", tags=["administration"])
logger = get_logger(component="legacy_identity_migration")


async def _identity_responses(database: AsyncSession) -> list[LegacyIdentityResponse]:
    identities = list(
        await database.scalars(
            select(LegacyIdentity).order_by(LegacyIdentity.captured_at, LegacyIdentity.id)
        )
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
            .where(
                LegacyIdentityMapping.legacy_identity_id.in_(identity_ids),
                LegacyIdentityMapping.revoked_at.is_(None),
            )
        )
    ).all()
    now = utc_now()
    usable_accounts = {
        mapping.legacy_identity_id: (
            user.is_active
            and user.username is not None
            and user.password_hash is not None
            and not user.must_change_password
            and (user.password_expires_at is None or as_utc(user.password_expires_at) > now)
        )
        for mapping, user in mapping_rows
    }
    mappings = {
        mapping.legacy_identity_id: LegacyMappingSummary(
            id=mapping.id,
            application_user_id=user.id,
            username=user.username or "",
            display_name=user.display_name,
            mapped_by_application_user_id=mapping.mapped_by_application_user_id,
            mapped_at=mapping.mapped_at,
            last_reconciled_at=mapping.last_reconciled_at,
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
            status=(
                LegacyIdentityStatus.UNMAPPED
                if identity.id not in mappings
                else LegacyIdentityStatus.READY
                if usable_accounts[identity.id]
                else LegacyIdentityStatus.ACTIVATION_PENDING
            ),
        )
        for identity in identities
    ]


def _migration_state_hash(identities: list[LegacyIdentityResponse]) -> str:
    state = [identity.model_dump(mode="json") for identity in identities]
    encoded = json.dumps(state, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _review_summary(review: LegacyMigrationReview) -> LegacyMigrationReviewSummary:
    return LegacyMigrationReviewSummary(
        id=review.id,
        reviewed_by_application_user_id=review.reviewed_by_application_user_id,
        reviewed_at=review.reviewed_at,
        unresolved_identity_ids=[uuid.UUID(value) for value in review.unresolved_identity_ids],
        accepted_login_loss=review.accepted_login_loss,
    )


async def _list_response(database: AsyncSession) -> LegacyIdentityListResponse:
    identities = await _identity_responses(database)
    unresolved_count = sum(identity.status != LegacyIdentityStatus.READY for identity in identities)
    latest_review = await database.scalar(
        select(LegacyMigrationReview)
        .order_by(LegacyMigrationReview.reviewed_at.desc(), LegacyMigrationReview.id.desc())
        .limit(1)
    )
    active_review = (
        _review_summary(latest_review)
        if latest_review is not None
        and latest_review.migration_state_hash == _migration_state_hash(identities)
        else None
    )
    return LegacyIdentityListResponse(
        identities=identities,
        unresolved_count=unresolved_count,
        activation_pending_count=sum(
            identity.status == LegacyIdentityStatus.ACTIVATION_PENDING for identity in identities
        ),
        cutover_ready=active_review is not None
        and (unresolved_count == 0 or active_review.accepted_login_loss),
        active_review=active_review,
    )


@router.get("", response_model=LegacyIdentityListResponse)
async def list_legacy_identities(
    _: ApplicationUser = Depends(require_global_admin),
    database: AsyncSession = Depends(get_session),
) -> LegacyIdentityListResponse:
    return await _list_response(database)


@router.post("/review", response_model=LegacyIdentityListResponse)
async def record_migration_review(
    payload: LegacyMigrationReviewRequest,
    actor: ApplicationUser = Depends(require_global_admin),
    database: AsyncSession = Depends(get_session),
) -> LegacyIdentityListResponse:
    identities = await _identity_responses(database)
    unresolved_ids = {
        identity.id for identity in identities if identity.status != LegacyIdentityStatus.READY
    }
    provided_ids = set(payload.unresolved_identity_ids)
    if len(provided_ids) != len(payload.unresolved_identity_ids) or provided_ids != unresolved_ids:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Migration state changed; refresh before completing the review",
        )
    if unresolved_ids and not payload.accept_login_loss:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Explicit acceptance is required while legacy logins remain unresolved",
        )
    review = LegacyMigrationReview(
        reviewed_by_application_user_id=actor.id,
        reviewed_at=utc_now(),
        unresolved_identity_ids=sorted(str(identity_id) for identity_id in unresolved_ids),
        accepted_login_loss=payload.accept_login_loss,
        migration_state_hash=_migration_state_hash(identities),
    )
    database.add(review)
    await database.commit()
    logger.warning(
        "legacy_migration_review_recorded",
        actor_user_id=str(actor.id),
        accepted_login_loss=payload.accept_login_loss,
        unresolved_identity_ids=review.unresolved_identity_ids,
    )
    return await _list_response(database)


@router.get("/reviews", response_model=LegacyMigrationReviewHistory)
async def migration_review_history(
    _: ApplicationUser = Depends(require_global_admin),
    database: AsyncSession = Depends(get_session),
) -> LegacyMigrationReviewHistory:
    reviews = list(
        await database.scalars(
            select(LegacyMigrationReview).order_by(LegacyMigrationReview.reviewed_at.desc())
        )
    )
    return LegacyMigrationReviewHistory(reviews=[_review_summary(review) for review in reviews])


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
        select(LegacyIdentityMapping).where(
            LegacyIdentityMapping.legacy_identity_id == identity.id,
            LegacyIdentityMapping.revoked_at.is_(None),
        )
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
    if account.id == identity.source_application_user_id:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Legacy identities must map to a separate local account",
        )

    mapping = LegacyIdentityMapping(
        legacy_identity_id=identity.id,
        application_user_id=account.id,
        mapped_by_application_user_id=actor.id,
    )
    database.add(mapping)
    await database.flush()
    transferred_household_count = await reconcile_mapping(database, mapping)
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
        transferred_household_count=transferred_household_count,
    )
    identities = await _identity_responses(database)
    mapped_identity = next(item for item in identities if item.id == identity.id)
    return LegacyIdentityMappedResponse(
        identity=mapped_identity,
        temporary_password=temporary_password,
    )


@router.post("/reconcile", response_model=LegacyIdentityListResponse)
async def reconcile_legacy_memberships(
    actor: ApplicationUser = Depends(require_global_admin),
    database: AsyncSession = Depends(get_session),
) -> LegacyIdentityListResponse:
    mappings = list(
        await database.scalars(
            select(LegacyIdentityMapping)
            .where(LegacyIdentityMapping.revoked_at.is_(None))
            .with_for_update()
        )
    )
    for mapping in mappings:
        await reconcile_mapping(database, mapping)
    await database.commit()
    logger.info(
        "legacy_memberships_reconciled",
        actor_user_id=str(actor.id),
        mapping_count=len(mappings),
    )
    return await _list_response(database)


@router.delete("/{legacy_identity_id}/mapping", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_legacy_mapping(
    legacy_identity_id: uuid.UUID,
    actor: ApplicationUser = Depends(require_global_admin),
    database: AsyncSession = Depends(get_session),
) -> None:
    mapping = await database.scalar(
        select(LegacyIdentityMapping)
        .where(
            LegacyIdentityMapping.legacy_identity_id == legacy_identity_id,
            LegacyIdentityMapping.revoked_at.is_(None),
        )
        .with_for_update()
    )
    if mapping is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Active identity mapping not found")
    mapping.revoked_at = utc_now()
    mapping.revoked_by_application_user_id = actor.id
    await revoke_mapping_memberships(database, mapping)
    await database.commit()
    logger.warning(
        "legacy_identity_mapping_revoked",
        actor_user_id=str(actor.id),
        legacy_identity_id=str(legacy_identity_id),
        target_user_id=str(mapping.application_user_id),
    )


@router.get(
    "/{legacy_identity_id}/mapping-history",
    response_model=LegacyMappingHistoryResponse,
)
async def legacy_mapping_history(
    legacy_identity_id: uuid.UUID,
    _: ApplicationUser = Depends(require_global_admin),
    database: AsyncSession = Depends(get_session),
) -> LegacyMappingHistoryResponse:
    rows = (
        await database.execute(
            select(LegacyIdentityMapping, ApplicationUser)
            .join(ApplicationUser, ApplicationUser.id == LegacyIdentityMapping.application_user_id)
            .where(LegacyIdentityMapping.legacy_identity_id == legacy_identity_id)
            .order_by(LegacyIdentityMapping.mapped_at)
        )
    ).all()
    return LegacyMappingHistoryResponse(
        mappings=[
            LegacyMappingSummary(
                id=mapping.id,
                application_user_id=user.id,
                username=user.username or "",
                display_name=user.display_name,
                mapped_by_application_user_id=mapping.mapped_by_application_user_id,
                mapped_at=mapping.mapped_at,
                last_reconciled_at=mapping.last_reconciled_at,
                revoked_at=mapping.revoked_at,
                revoked_by_application_user_id=mapping.revoked_by_application_user_id,
            )
            for mapping, user in rows
        ]
    )
