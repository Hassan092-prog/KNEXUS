"""Explicit idempotent seed for the server-owned synthetic Phase 1 actor."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.demo_identity import build_demo_actor
from app.schemas import ActorContext
from app.models import Organization, User

_DEMO_ORG_NAME = "KNEXUS Demo Organization"
_DEMO_ORG_SLUG = "knexus-demo"
_DEMO_EMAIL = "demo@knexus.invalid"
_DEMO_FULL_NAME = "KNEXUS Demo User"


class DemoSeedConflictError(RuntimeError):
    """A reserved demo UUID already belongs to a different persisted record."""


def build_demo_records() -> tuple[Organization, User]:
    """Build synthetic rows with IDs matching the canonical actor fixture."""
    actor = build_demo_actor()
    return (
        Organization(
            id=actor.org_id, name=_DEMO_ORG_NAME, slug=_DEMO_ORG_SLUG, is_active=True
        ),
        User(
            id=actor.user_id,
            org_id=actor.org_id,
            email=_DEMO_EMAIL,
            full_name=_DEMO_FULL_NAME,
            role="orgadmin",
            is_active=True,
            is_demo=True,
        ),
    )


async def seed_demo_identity(session: AsyncSession) -> ActorContext:
    """Add the reserved demo organization/user inside the caller's transaction.

    This function only flushes. The caller controls commit/rollback and must
    invoke it explicitly; application startup never seeds records implicitly.
    """
    actor = build_demo_actor()
    organization_seed, user_seed = build_demo_records()

    organization = await session.get(Organization, actor.org_id)
    if organization is None:
        session.add(organization_seed)
        await session.flush()
    elif (
        organization.slug != _DEMO_ORG_SLUG
        or organization.name != _DEMO_ORG_NAME
        or not organization.is_active
    ):
        raise DemoSeedConflictError("Reserved demo organization ID is already in use")

    user = await session.get(User, actor.user_id)
    if user is None:
        session.add(user_seed)
        await session.flush()
    elif (
        user.org_id != actor.org_id
        or user.role != "orgadmin"
        or not user.is_demo
        or not user.is_active
    ):
        raise DemoSeedConflictError("Reserved demo user ID is already in use")

    return actor
