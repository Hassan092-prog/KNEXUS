"""Synthetic server-owned identity for local Phase 1 development only."""
from uuid import UUID

from app.schemas import ActorContext, Role

# These identifiers match the checked-in synthetic actor-context fixture.
_DEMO_USER_ID = UUID("00000000-0000-4000-8000-000000000031")
_DEMO_ORG_ID = UUID("00000000-0000-4000-8000-000000000032")
_ROLE_INHERITANCE: dict[Role, tuple[Role, ...]] = {
    "employee": ("employee",),
    "manager": ("manager", "employee"),
    "orgadmin": ("orgadmin", "manager", "employee"),
    "superadmin": ("superadmin", "orgadmin", "manager", "employee"),
}


def expand_effective_roles(primary_role: Role) -> list[Role]:
    """Return the documented role hierarchy for a server-selected role."""
    try:
        return list(_ROLE_INHERITANCE[primary_role])
    except KeyError as exc:
        raise ValueError(f"Unsupported demo role: {primary_role!r}") from exc


def build_demo_actor(primary_role: Role = "orgadmin") -> ActorContext:
    """Create the fixed synthetic actor; this function does not authenticate users."""
    return ActorContext(
        user_id=_DEMO_USER_ID,
        org_id=_DEMO_ORG_ID,
        effective_roles=expand_effective_roles(primary_role),
    )
