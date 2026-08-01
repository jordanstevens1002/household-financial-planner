"""Provenance-aware reconciliation for memberships inherited from legacy identities."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.accounts.sessions import utc_now
from app.core.dependencies import ROLE_LEVEL
from app.models import (
    HouseholdMembership,
    LegacyIdentity,
    LegacyIdentityMapping,
    LegacyMembershipBaseline,
    LegacyMembershipGrant,
)


async def _baseline(
    database: AsyncSession,
    application_user_id: uuid.UUID,
    household_id: uuid.UUID,
) -> LegacyMembershipBaseline:
    baseline = await database.scalar(
        select(LegacyMembershipBaseline).where(
            LegacyMembershipBaseline.application_user_id == application_user_id,
            LegacyMembershipBaseline.household_id == household_id,
        )
    )
    if baseline is not None:
        return baseline
    membership = await database.scalar(
        select(HouseholdMembership).where(
            HouseholdMembership.application_user_id == application_user_id,
            HouseholdMembership.household_id == household_id,
        )
    )
    baseline = LegacyMembershipBaseline(
        application_user_id=application_user_id,
        household_id=household_id,
        original_role=membership.role if membership else None,
    )
    database.add(baseline)
    await database.flush()
    return baseline


async def _apply_effective_role(
    database: AsyncSession,
    application_user_id: uuid.UUID,
    household_id: uuid.UUID,
) -> None:
    baseline = await _baseline(database, application_user_id, household_id)
    inherited_roles = list(
        await database.scalars(
            select(LegacyMembershipGrant.role)
            .join(
                LegacyIdentityMapping,
                LegacyIdentityMapping.id == LegacyMembershipGrant.legacy_identity_mapping_id,
            )
            .where(
                LegacyIdentityMapping.application_user_id == application_user_id,
                LegacyIdentityMapping.revoked_at.is_(None),
                LegacyMembershipGrant.household_id == household_id,
                LegacyMembershipGrant.is_active.is_(True),
            )
        )
    )
    roles = inherited_roles + ([baseline.original_role] if baseline.original_role else [])
    desired_role = max(roles, key=ROLE_LEVEL.__getitem__) if roles else None
    membership = await database.scalar(
        select(HouseholdMembership)
        .where(
            HouseholdMembership.application_user_id == application_user_id,
            HouseholdMembership.household_id == household_id,
        )
        .with_for_update()
    )
    if desired_role is None:
        if membership is not None:
            await database.delete(membership)
    elif membership is None:
        database.add(
            HouseholdMembership(
                application_user_id=application_user_id,
                household_id=household_id,
                role=desired_role,
            )
        )
    else:
        membership.role = desired_role


async def reconcile_mapping(
    database: AsyncSession,
    mapping: LegacyIdentityMapping,
) -> int:
    """Synchronise one mapping and return its active inherited-household count."""
    identity = await database.get(LegacyIdentity, mapping.legacy_identity_id)
    if identity is None:
        return 0
    source_memberships = {
        membership.household_id: membership
        for membership in await database.scalars(
            select(HouseholdMembership).where(
                HouseholdMembership.application_user_id == identity.source_application_user_id
            )
        )
    }
    grants = {
        grant.household_id: grant
        for grant in await database.scalars(
            select(LegacyMembershipGrant).where(
                LegacyMembershipGrant.legacy_identity_mapping_id == mapping.id
            )
        )
    }
    affected_households = set(source_memberships) | set(grants)
    for household_id in affected_households:
        await _baseline(database, mapping.application_user_id, household_id)
        source_membership = source_memberships.get(household_id)
        grant = grants.get(household_id)
        if source_membership is None:
            assert grant is not None
            grant.is_active = False
        elif grant is None:
            database.add(
                LegacyMembershipGrant(
                    legacy_identity_mapping_id=mapping.id,
                    household_id=household_id,
                    role=source_membership.role,
                )
            )
        else:
            grant.role = source_membership.role
            grant.is_active = True
    mapping.last_reconciled_at = utc_now()
    await database.flush()
    for household_id in affected_households:
        await _apply_effective_role(database, mapping.application_user_id, household_id)
    return len(source_memberships)


async def revoke_mapping_memberships(
    database: AsyncSession,
    mapping: LegacyIdentityMapping,
) -> None:
    grants = list(
        await database.scalars(
            select(LegacyMembershipGrant).where(
                LegacyMembershipGrant.legacy_identity_mapping_id == mapping.id
            )
        )
    )
    for grant in grants:
        grant.is_active = False
    await database.flush()
    for household_id in {grant.household_id for grant in grants}:
        await _apply_effective_role(database, mapping.application_user_id, household_id)
