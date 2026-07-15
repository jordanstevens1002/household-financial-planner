import uuid
from collections.abc import Callable

from fastapi import Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import Identity, get_identity
from app.database import get_session
from app.models import ApplicationUser, HouseholdMembership, HouseholdRole

ROLE_LEVEL = {
    HouseholdRole.VIEWER: 0,
    HouseholdRole.EDITOR: 1,
    HouseholdRole.ADMIN: 2,
    HouseholdRole.OWNER: 3,
}


async def current_user(
    identity: Identity = Depends(get_identity), session: AsyncSession = Depends(get_session)
) -> ApplicationUser:
    user = await session.scalar(
        select(ApplicationUser).where(ApplicationUser.oidc_subject == identity.subject)
    )
    if user is None:
        user = ApplicationUser(
            oidc_subject=identity.subject, email=identity.email, display_name=identity.display_name
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    return user


def require_household_role(minimum: HouseholdRole) -> Callable[..., object]:
    async def dependency(
        household_id: uuid.UUID,
        user: ApplicationUser = Depends(current_user),
        session: AsyncSession = Depends(get_session),
    ) -> HouseholdMembership:
        membership = await session.scalar(
            select(HouseholdMembership).where(
                HouseholdMembership.household_id == household_id,
                HouseholdMembership.application_user_id == user.id,
            )
        )
        if membership is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Household not found")
        if ROLE_LEVEL[membership.role] < ROLE_LEVEL[minimum]:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient household role")
        return membership

    return dependency
