"""Create the Phase 1 tenant and document persistence foundation.

Revision ID: 0001_phase1_persistence
Revises:
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "0001_phase1_persistence"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

ROLE_VALUES = "'employee', 'manager', 'orgadmin', 'superadmin'"
ROLE_ARRAY_JSON = (
    "'[\"employee\", \"manager\", \"orgadmin\", \"superadmin\"]'::jsonb"
)
DOCUMENT_STATES = "'queued', 'processing', 'complete', 'failed'"
FAILURE_CODES = "'INVALID_FILE', 'PROCESSING_FAILED', 'INTERRUPTED'"


def upgrade() -> None:
    # The extension is deliberately retained if this migration is downgraded.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "organizations",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_organizations_name_nonempty"),
        sa.CheckConstraint("length(trim(slug)) > 0", name="ck_organizations_slug_nonempty"),
        sa.PrimaryKeyConstraint("id", name="pk_organizations"),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )

    op.create_table(
        "users",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_demo", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"role IN ({ROLE_VALUES})", name="ck_users_role"),
        sa.CheckConstraint("length(trim(email)) > 0", name="ck_users_email_nonempty"),
        sa.ForeignKeyConstraint(
            ["org_id"], ["organizations.id"], name="fk_users_org_id", ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("org_id", "email", name="uq_users_org_email"),
        sa.UniqueConstraint("org_id", "id", name="uq_users_org_id_id"),
    )

    op.create_table(
        "documents",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("source_type", sa.String(20), nullable=False),
        sa.Column("original_filename", sa.String(512), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("allowed_roles", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'queued'"), nullable=False),
        sa.Column("chunk_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "metadata", postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"), nullable=False,
        ),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("source_type IN ('pdf', 'docx')", name="ck_documents_source_type"),
        sa.CheckConstraint(f"status IN ({DOCUMENT_STATES})", name="ck_documents_status"),
        sa.CheckConstraint("chunk_count >= 0", name="ck_documents_chunk_count"),
        sa.CheckConstraint(
            "file_size_bytes > 0 AND file_size_bytes <= 10485760",
            name="ck_documents_file_size",
        ),
        sa.CheckConstraint(
            "jsonb_typeof(allowed_roles) = 'array' "
            "AND jsonb_array_length(allowed_roles) > 0 "
            f"AND allowed_roles <@ {ROLE_ARRAY_JSON}",
            name="ck_documents_allowed_roles",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"], ["organizations.id"],
            name="fk_documents_org_id", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "uploaded_by"], ["users.org_id", "users.id"],
            name="fk_documents_uploader_same_org", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_documents"),
        sa.UniqueConstraint("org_id", "id", name="uq_documents_org_id_id"),
    )
    op.create_index("ix_documents_org_status", "documents", ["org_id", "status"])

    op.create_table(
        "document_chunks",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("page", sa.Integer(), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=True),
        sa.Column(
            "source_metadata", postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"), nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("chunk_index >= 0", name="ck_chunks_index"),
        sa.CheckConstraint("length(content) BETWEEN 1 AND 8000", name="ck_chunks_content"),
        sa.CheckConstraint("page IS NULL OR page >= 1", name="ck_chunks_page"),
        sa.CheckConstraint(
            "token_count IS NULL OR token_count >= 0", name="ck_chunks_token_count"
        ),
        sa.ForeignKeyConstraint(
            ["org_id"], ["organizations.id"],
            name="fk_chunks_org_id", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "document_id"], ["documents.org_id", "documents.id"],
            name="fk_chunks_document_same_org", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_document_chunks"),
        sa.UniqueConstraint(
            "org_id", "document_id", "chunk_index",
            name="uq_chunks_org_document_position",
        ),
        sa.UniqueConstraint("org_id", "document_id", "id", name="uq_chunks_org_document_id"),
    )
    op.create_index(
        "ix_chunks_org_document", "document_chunks", ["org_id", "document_id"]
    )

    op.create_table(
        "embeddings",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("embedding", Vector(384), nullable=False),
        sa.Column("model_name", sa.String(128), nullable=False),
        sa.Column("model_revision", sa.String(128), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(trim(model_name)) > 0", name="ck_embeddings_model_name"),
        sa.CheckConstraint(
            "length(trim(model_revision)) > 0", name="ck_embeddings_model_revision"
        ),
        sa.ForeignKeyConstraint(
            ["org_id"], ["organizations.id"],
            name="fk_embeddings_org_id", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "document_id", "chunk_id"],
            ["document_chunks.org_id", "document_chunks.document_id", "document_chunks.id"],
            name="fk_embeddings_chunk_same_org_document", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_embeddings"),
        sa.UniqueConstraint(
            "chunk_id", "model_name", "model_revision",
            name="uq_embeddings_chunk_model_revision",
        ),
    )
    op.create_index(
        "ix_embeddings_org_document", "embeddings", ["org_id", "document_id"]
    )
    op.create_index(
        "uq_embeddings_active_chunk", "embeddings", ["chunk_id"],
        unique=True, postgresql_where=sa.text("is_active"),
    )
    op.create_index(
        "ix_embeddings_vector_hnsw", "embeddings", ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
        postgresql_with={"m": 16, "ef_construction": 64},
    )

    op.create_table(
        "ingestion_jobs",
        sa.Column(
            "id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("org_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(20), server_default=sa.text("'queued'"), nullable=False),
        sa.Column("chunks_processed", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("total_chunks", sa.Integer(), nullable=True),
        sa.Column("failure_code", sa.String(32), nullable=True),
        sa.Column("failure_message", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"status IN ({DOCUMENT_STATES})", name="ck_jobs_status"),
        sa.CheckConstraint("attempt_number >= 1", name="ck_jobs_attempt_number"),
        sa.CheckConstraint(
            "chunks_processed >= 0 AND "
            "(total_chunks IS NULL OR total_chunks >= chunks_processed)",
            name="ck_jobs_chunk_counts",
        ),
        sa.CheckConstraint(
            f"failure_code IS NULL OR failure_code IN ({FAILURE_CODES})",
            name="ck_jobs_failure_code",
        ),
        # PostgreSQL POSIX [:space:] treats space, tab, LF, VT, FF, and CR as whitespace.
        sa.CheckConstraint(
            "(status <> 'queued' OR "
            "(started_at IS NULL AND finished_at IS NULL AND chunks_processed = 0)) "
            "AND (status <> 'processing' OR "
            "(started_at IS NOT NULL AND finished_at IS NULL AND failure_code IS NULL "
            "AND failure_message IS NULL)) "
            "AND (status <> 'complete' OR "
            "(started_at IS NOT NULL AND finished_at IS NOT NULL "
            "AND total_chunks IS NOT NULL AND chunks_processed = total_chunks "
            "AND failure_code IS NULL AND failure_message IS NULL)) "
            "AND (status = 'failed' OR "
            "(failure_code IS NULL AND failure_message IS NULL)) "
            "AND (status <> 'failed' OR "
            "(finished_at IS NOT NULL AND failure_code IS NOT NULL "
            "AND failure_message IS NOT NULL "
            "AND failure_message ~ '[^[:space:]]'))",
            name="ck_jobs_state_consistency",
        ),
        sa.ForeignKeyConstraint(
            ["org_id"], ["organizations.id"],
            name="fk_jobs_org_id", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["org_id", "document_id"], ["documents.org_id", "documents.id"],
            name="fk_jobs_document_same_org", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_ingestion_jobs"),
        sa.UniqueConstraint(
            "org_id", "document_id", "attempt_number",
            name="uq_jobs_org_document_attempt",
        ),
    )
    op.create_index(
        "ix_jobs_latest_attempt",
        "ingestion_jobs",
        ["org_id", "document_id", "attempt_number"],
    )
    op.create_index(
        "uq_jobs_one_active_per_document",
        "ingestion_jobs",
        ["org_id", "document_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'processing')"),
    )


def downgrade() -> None:
    op.drop_table("ingestion_jobs")
    op.drop_table("embeddings")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("users")
    op.drop_table("organizations")
    # Keep the pgvector extension: it may be shared by other database objects.
