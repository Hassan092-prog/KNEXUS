"""Core tenant and demo user models for the Phase 1 database."""
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKeyConstraint, PrimaryKeyConstraint, String, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Organization(Base):
    """Tenant boundary for users and all organization-owned records."""

    __tablename__ = "organizations"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_organizations"),
        UniqueConstraint("slug", name="uq_organizations_slug"),
        CheckConstraint("length(trim(name)) > 0", name="ck_organizations_name_nonempty"),
        CheckConstraint("length(trim(slug)) > 0", name="ck_organizations_slug_nonempty"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class User(Base):
    """A tenant-scoped user record; Phase 1 seeds only the server demo actor."""

    __tablename__ = "users"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_users"),
        UniqueConstraint("org_id", "id", name="uq_users_org_id_id"),
        UniqueConstraint("org_id", "email", name="uq_users_org_email"),
        CheckConstraint(
            "role IN ('employee', 'manager', 'orgadmin', 'superadmin')",
            name="ck_users_role",
        ),
        CheckConstraint("length(trim(email)) > 0", name="ck_users_email_nonempty"),
        ForeignKeyConstraint(
            ["org_id"], ["organizations.id"],
            name="fk_users_org_id", ondelete="RESTRICT",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    org_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    is_demo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
