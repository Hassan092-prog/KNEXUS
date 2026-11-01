"""Document, chunk, embedding and persisted ingestion-job models."""
from datetime import datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Integer,
    PrimaryKeyConstraint,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base

VECTOR_DIMENSIONS = 384
_ALLOWED_ROLES_JSON = (
    "'[\"employee\", \"manager\", \"orgadmin\", \"superadmin\"]'::jsonb"
)


class Document(Base):
    """Tenant-owned source document and its Phase 1 lifecycle state."""

    __tablename__ = "documents"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_documents"),
        UniqueConstraint("org_id", "id", name="uq_documents_org_id_id"),
        CheckConstraint(
            "source_type IN ('pdf', 'docx')", name="ck_documents_source_type"
        ),
        CheckConstraint(
            "status IN ('queued', 'processing', 'complete', 'failed')",
            name="ck_documents_status",
        ),
        CheckConstraint("chunk_count >= 0", name="ck_documents_chunk_count"),
        CheckConstraint(
            "file_size_bytes > 0 AND file_size_bytes <= 10485760",
            name="ck_documents_file_size",
        ),
        CheckConstraint(
            f"jsonb_typeof(allowed_roles) = 'array' "
            f"AND jsonb_array_length(allowed_roles) > 0 "
            f"AND allowed_roles <@ {_ALLOWED_ROLES_JSON}",
            name="ck_documents_allowed_roles",
        ),
        ForeignKeyConstraint(
            ["org_id"], ["organizations.id"],
            name="fk_documents_org_id", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["org_id", "uploaded_by"], ["users.org_id", "users.id"],
            name="fk_documents_uploader_same_org", ondelete="RESTRICT",
        ),
        Index("ix_documents_org_status", "org_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    org_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    uploaded_by: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    storage_key: Mapped[str | None] = mapped_column(String(512))
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    allowed_roles: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued", server_default=text("'queued'")
    )
    chunk_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    description: Mapped[str | None] = mapped_column(Text)
    metadata_json: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict,
        server_default=text("'{}'::jsonb"),
    )
    is_deleted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class DocumentChunk(Base):
    """Stable document segment and parser source-location metadata."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_document_chunks"),
        UniqueConstraint(
            "org_id", "document_id", "chunk_index",
            name="uq_chunks_org_document_position",
        ),
        UniqueConstraint(
            "org_id", "document_id", "id",
            name="uq_chunks_org_document_id",
        ),
        CheckConstraint("chunk_index >= 0", name="ck_chunks_index"),
        CheckConstraint("length(content) BETWEEN 1 AND 8000", name="ck_chunks_content"),
        CheckConstraint(
            "page IS NULL OR page >= 1", name="ck_chunks_page"
        ),
        CheckConstraint(
            "token_count IS NULL OR token_count >= 0", name="ck_chunks_token_count"
        ),
        ForeignKeyConstraint(
            ["org_id"], ["organizations.id"],
            name="fk_chunks_org_id", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["org_id", "document_id"], ["documents.org_id", "documents.id"],
            name="fk_chunks_document_same_org", ondelete="CASCADE",
        ),
        Index("ix_chunks_org_document", "org_id", "document_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    org_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    page: Mapped[int | None] = mapped_column(Integer)
    token_count: Mapped[int | None] = mapped_column(Integer)
    source_metadata: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Embedding(Base):
    """384-dimensional vector tied to a tenant's exact document chunk."""

    __tablename__ = "embeddings"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_embeddings"),
        UniqueConstraint(
            "chunk_id", "model_name", "model_revision",
            name="uq_embeddings_chunk_model_revision",
        ),
        CheckConstraint("length(trim(model_name)) > 0", name="ck_embeddings_model_name"),
        CheckConstraint(
            "length(trim(model_revision)) > 0", name="ck_embeddings_model_revision"
        ),
        ForeignKeyConstraint(
            ["org_id"], ["organizations.id"],
            name="fk_embeddings_org_id", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["org_id", "document_id", "chunk_id"],
            ["document_chunks.org_id", "document_chunks.document_id", "document_chunks.id"],
            name="fk_embeddings_chunk_same_org_document", ondelete="CASCADE",
        ),
        Index("ix_embeddings_org_document", "org_id", "document_id"),
        Index(
            "uq_embeddings_active_chunk",
            "chunk_id",
            unique=True,
            postgresql_where=text("is_active"),
        ),
        Index(
            "ix_embeddings_vector_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_with={"m": 16, "ef_construction": 64},
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    org_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    chunk_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(VECTOR_DIMENSIONS), nullable=False)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    model_revision: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class IngestionJob(Base):
    """Persisted attempt backing the public document status and task ID."""

    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        PrimaryKeyConstraint("id", name="pk_ingestion_jobs"),
        UniqueConstraint(
            "org_id", "document_id", "attempt_number",
            name="uq_jobs_org_document_attempt",
        ),
        CheckConstraint(
            "status IN ('queued', 'processing', 'complete', 'failed')",
            name="ck_jobs_status",
        ),
        CheckConstraint("attempt_number >= 1", name="ck_jobs_attempt_number"),
        CheckConstraint(
            "chunks_processed >= 0 AND "
            "(total_chunks IS NULL OR total_chunks >= chunks_processed)",
            name="ck_jobs_chunk_counts",
        ),
        CheckConstraint(
            "failure_code IS NULL OR failure_code IN "
            "('INVALID_FILE', 'PROCESSING_FAILED', 'INTERRUPTED')",
            name="ck_jobs_failure_code",
        ),
        # PostgreSQL POSIX [:space:] treats space, tab, LF, VT, FF, and CR as whitespace.
        CheckConstraint(
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
        ForeignKeyConstraint(
            ["org_id"], ["organizations.id"],
            name="fk_jobs_org_id", ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["org_id", "document_id"], ["documents.org_id", "documents.id"],
            name="fk_jobs_document_same_org", ondelete="CASCADE",
        ),
        Index("ix_jobs_latest_attempt", "org_id", "document_id", "attempt_number"),
        Index(
            "uq_jobs_one_active_per_document",
            "org_id",
            "document_id",
            unique=True,
            postgresql_where=text("status IN ('queued', 'processing')"),
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4,
        server_default=text("gen_random_uuid()"),
    )
    org_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    document_id: Mapped[UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued", server_default=text("'queued'")
    )
    chunks_processed: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    total_chunks: Mapped[int | None] = mapped_column(Integer)
    failure_code: Mapped[str | None] = mapped_column(String(32))
    failure_message: Mapped[str | None] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
