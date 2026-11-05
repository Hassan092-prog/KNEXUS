"""Database metadata and demo seed checks that require no database connection."""
import ast
import json
from datetime import datetime
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import ValidationError
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint, DateTime, ForeignKeyConstraint, UniqueConstraint,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.schema import CreateIndex, CreateTable

from app.core.config import REPOSITORY_ENV_FILE, Settings
from app.core.database import Base
from app.db.demo_seed import (
    DemoSeedConflictError,
    build_demo_records,
    seed_demo_identity,
)
from app.schemas import DocumentStatus
from app.models import (
    VECTOR_DIMENSIONS,
    Document,
    DocumentChunk,
    Embedding,
    IngestionJob,
    Organization,
    User,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _attribute_name(node):
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return f"{_attribute_name(node.value)}.{node.attr}"
    return ""


def _migration_check_expression(table_name, constraint_name):
    source = (REPO_ROOT / "backend/alembic/versions/0001_phase1_persistence.py").read_text()
    tree = ast.parse(source)
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call) or _attribute_name(call.func) != "op.create_table":
            continue
        if ast.literal_eval(call.args[0]) != table_name:
            continue
        for constraint in call.args[1:]:
            if not isinstance(constraint, ast.Call):
                continue
            if _attribute_name(constraint.func) != "sa.CheckConstraint":
                continue
            name = next(
                (ast.literal_eval(kw.value) for kw in constraint.keywords if kw.arg == "name"),
                None,
            )
            if name == constraint_name:
                return ast.literal_eval(constraint.args[0])
    raise AssertionError(f"Migration check {constraint_name} was not found")


def _migration_timestamp_columns():
    source = (REPO_ROOT / "backend/alembic/versions/0001_phase1_persistence.py").read_text()
    tree = ast.parse(source)
    result = {}
    for call in ast.walk(tree):
        if not isinstance(call, ast.Call) or _attribute_name(call.func) != "op.create_table":
            continue
        table_name = ast.literal_eval(call.args[0])
        for column_call in call.args[1:]:
            if not isinstance(column_call, ast.Call):
                continue
            if _attribute_name(column_call.func) != "sa.Column":
                continue
            column_name = ast.literal_eval(column_call.args[0])
            date_type = next(
                (node for node in ast.walk(column_call)
                 if isinstance(node, ast.Call)
                 and _attribute_name(node.func) == "sa.DateTime"),
                None,
            )
            if date_type is not None:
                timezone = next(
                    (kw.value for kw in date_type.keywords if kw.arg == "timezone"),
                    ast.Constant(value=False),
                )
                result[(table_name, column_name)] = ast.literal_eval(timezone)
    return result


def test_all_phase_one_tables_are_registered_on_application_metadata():
    assert set(Base.metadata.tables) == {
        "organizations",
        "users",
        "documents",
        "document_chunks",
        "embeddings",
        "ingestion_jobs",
    }


def test_orm_timestamp_types_match_timezone_aware_migration_columns():
    model_timestamps = {
        (table.name, column.name): column.type.timezone
        for table in Base.metadata.tables.values()
        for column in table.columns
        if isinstance(column.type, DateTime)
    }
    migration_timestamps = _migration_timestamp_columns()

    assert migration_timestamps == model_timestamps
    assert model_timestamps
    assert all(model_timestamps.values())


def test_settings_env_file_is_repository_rooted_and_env_overrides_dotenv(tmp_path, monkeypatch):
    assert REPOSITORY_ENV_FILE.is_absolute()
    assert REPOSITORY_ENV_FILE == REPO_ROOT / ".env"
    assert Settings.model_config["env_file"] == REPOSITORY_ENV_FILE

    synthetic_root = tmp_path / "synthetic-repo"
    synthetic_root.mkdir()
    dotenv_file = synthetic_root / ".env"
    dotenv_file.write_text(
        "DATABASE_URL=postgresql+asyncpg://dotenv_user:dotenv_pass@127.0.0.1/dotenv_db\n",
        encoding="utf-8",
    )
    first_cwd = tmp_path / "launch-one"
    second_cwd = tmp_path / "launch-two"
    first_cwd.mkdir()
    second_cwd.mkdir()

    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.chdir(first_cwd)
    first = Settings(_env_file=dotenv_file)
    monkeypatch.chdir(second_cwd)
    second = Settings(_env_file=dotenv_file)
    assert first.DATABASE_URL == second.DATABASE_URL
    assert first.DATABASE_URL.endswith("/dotenv_db")

    override = "postgresql+asyncpg://env_user:env_pass@127.0.0.1/env_db"
    monkeypatch.setenv("DATABASE_URL", override)
    assert Settings(_env_file=dotenv_file).DATABASE_URL == override


def test_models_compile_as_postgresql_ddl_without_connecting():
    for table in Base.metadata.sorted_tables:
        sql = str(CreateTable(table).compile(dialect=postgresql.dialect()))
        assert f"CREATE TABLE {table.name}" in sql
        assert "PRIMARY KEY" in sql


def test_document_and_chunk_keep_stable_ids_and_source_metadata():
    assert isinstance(Document.__table__.c.id.type, PGUUID)
    assert Document.__table__.c.id.type.as_uuid is True
    assert {"original_filename", "storage_key", "file_size_bytes", "metadata"}.issubset(
        Document.__table__.c.keys()
    )
    assert isinstance(DocumentChunk.__table__.c.id.type, PGUUID)
    assert DocumentChunk.__table__.c.id.type.as_uuid is True
    assert isinstance(DocumentChunk.__table__.c.source_metadata.type, JSONB)
    assert {"page", "token_count", "source_metadata"}.issubset(
        DocumentChunk.__table__.c.keys()
    )


def test_vector_is_fixed_at_agreed_384_dimensions_and_has_cosine_hnsw_index():
    vector_column = Embedding.__table__.c.embedding
    assert isinstance(vector_column.type, Vector)
    assert vector_column.type.dim == VECTOR_DIMENSIONS == 384

    hnsw = next(
        index for index in Embedding.__table__.indexes
        if index.name == "ix_embeddings_vector_hnsw"
    )
    sql = str(CreateIndex(hnsw).compile(dialect=postgresql.dialect()))
    assert "USING hnsw" in sql
    assert "vector_cosine_ops" in sql
    assert "m = 16" in sql and "ef_construction = 64" in sql


def _foreign_key(table, name):
    return next(
        constraint
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint) and constraint.name == name
    )


def test_child_rows_enforce_same_organization_parentage():
    document_uploader = _foreign_key(Document.__table__, "fk_documents_uploader_same_org")
    assert [element.parent.name for element in document_uploader.elements] == [
        "org_id", "uploaded_by"
    ]
    assert [element.target_fullname for element in document_uploader.elements] == [
        "users.org_id", "users.id"
    ]

    chunk_document = _foreign_key(DocumentChunk.__table__, "fk_chunks_document_same_org")
    assert [element.parent.name for element in chunk_document.elements] == [
        "org_id", "document_id"
    ]
    assert [element.target_fullname for element in chunk_document.elements] == [
        "documents.org_id", "documents.id"
    ]

    embedding_chunk = _foreign_key(
        Embedding.__table__, "fk_embeddings_chunk_same_org_document"
    )
    assert [element.target_fullname for element in embedding_chunk.elements] == [
        "document_chunks.org_id",
        "document_chunks.document_id",
        "document_chunks.id",
    ]

    job_document = _foreign_key(IngestionJob.__table__, "fk_jobs_document_same_org")
    assert [element.target_fullname for element in job_document.elements] == [
        "documents.org_id", "documents.id"
    ]


def test_document_roles_and_lifecycle_are_checked_in_schema():
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in Document.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert "ck_documents_allowed_roles" in checks
    assert "jsonb_array_length" in checks["ck_documents_allowed_roles"]
    assert "superadmin" in checks["ck_documents_allowed_roles"]
    assert "ck_documents_status" in checks
    assert all(state in checks["ck_documents_status"] for state in (
        "queued", "processing", "complete", "failed"
    ))


def test_chunk_positions_and_embedding_versions_are_unique():
    chunk_unique = {
        tuple(column.name for column in constraint.columns)
        for constraint in DocumentChunk.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("org_id", "document_id", "chunk_index") in chunk_unique

    embedding_unique = {
        tuple(column.name for column in constraint.columns)
        for constraint in Embedding.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    assert ("chunk_id", "model_name", "model_revision") in embedding_unique

    active_index = next(
        index for index in Embedding.__table__.indexes
        if index.name == "uq_embeddings_active_chunk"
    )
    assert active_index.unique is True
    assert str(active_index.dialect_options["postgresql"]["where"]) == "is_active"


def test_job_attempt_state_constraints_cover_progress_and_safe_failure():
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in IngestionJob.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }
    assert "ck_jobs_state_consistency" in checks
    assert "chunks_processed = total_chunks" in checks["ck_jobs_state_consistency"]
    assert "failure_code IS NOT NULL" in checks["ck_jobs_state_consistency"]
    assert "status = 'failed' OR" in checks["ck_jobs_state_consistency"]
    assert "failure_code IS NULL AND failure_message IS NULL" in checks[
        "ck_jobs_state_consistency"
    ]
    assert "failure_message ~ '[^[:space:]]'" in checks[
        "ck_jobs_state_consistency"
    ]
    assert checks["ck_jobs_state_consistency"] == _migration_check_expression(
        "ingestion_jobs", "ck_jobs_state_consistency"
    )
    assert "INTERRUPTED" in checks["ck_jobs_failure_code"]


@pytest.mark.parametrize("status", ["queued", "processing", "complete"])
def test_contract_rejects_failure_fields_for_nonfailed_jobs(status):
    values = {
        "document_id": "00000000-0000-4000-8000-000000000041",
        "status": status,
        "chunks_processed": 0,
        "failure_code": "PROCESSING_FAILED",
        "failure_message": "Safe public failure.",
    }
    if status == "complete":
        values.update(total_chunks=0, progress_percent=100)
    with pytest.raises(ValidationError):
        DocumentStatus.model_validate(values)


def test_contract_rejects_whitespace_only_failed_message():
    with pytest.raises(ValidationError):
        DocumentStatus.model_validate({
            "document_id": "00000000-0000-4000-8000-000000000041",
            "status": "failed",
            "chunks_processed": 0,
            "failure_code": "PROCESSING_FAILED",
            "failure_message": "   ",
        })



@pytest.mark.parametrize(
    ("failure_message", "has_non_whitespace"),
    [
        pytest.param("", False, id="empty"),
        pytest.param("   ", False, id="spaces-only"),
        pytest.param("\t\t", False, id="tabs-only"),
        pytest.param("\r\n\r\n", False, id="cr-lf-only"),
        pytest.param(" \t\r\n\v\f", False, id="mixed-whitespace"),
        pytest.param(" \tProcessing failed.\r\n ", True, id="text-surrounded-by-whitespace"),
    ],
)
def test_ascii_posix_whitespace_policy_cases(failure_message, has_non_whitespace):
    # Offline equivalent of PostgreSQL POSIX [[:space:]] for ASCII whitespace.
    # These cases do not execute or prove database CHECK constraint enforcement.
    postgres_ascii_whitespace = frozenset(" \t\n\r\f\v")
    actual = any(character not in postgres_ascii_whitespace for character in failure_message)
    assert actual is has_non_whitespace


def test_demo_records_match_the_server_owned_actor_fixture():
    actor = json.loads(
        (REPO_ROOT / "contracts/phase1/examples/actor-context.json").read_text()
    )
    organization, user = build_demo_records()

    assert organization.id == UUID(actor["org_id"])
    assert user.id == UUID(actor["user_id"])
    assert user.org_id == organization.id
    assert user.role == "orgadmin"
    assert user.is_demo is True
    assert user.email.endswith(".invalid")


class MemorySession:
    """Tiny unit-test double; it stores objects in memory and never opens a DB."""

    def __init__(self):
        self.rows = {}
        self.pending = []

    async def get(self, model, identifier):
        return self.rows.get((model, identifier))

    def add(self, row):
        self.pending.append(row)

    async def flush(self):
        for row in self.pending:
            self.rows[(type(row), row.id)] = row
        self.pending.clear()


@pytest.mark.asyncio
async def test_demo_seed_is_idempotent_and_leaves_transaction_to_caller():
    session = MemorySession()

    first = await seed_demo_identity(session)
    second = await seed_demo_identity(session)

    assert first == second
    assert len(session.rows) == 2
    assert (Organization, first.org_id) in session.rows
    assert (User, first.user_id) in session.rows
    assert session.rows[(User, first.user_id)].role == "orgadmin"


@pytest.mark.asyncio
async def test_demo_seed_rejects_a_reserved_id_owned_by_another_organization():
    session = MemorySession()
    organization, _ = build_demo_records()
    organization.slug = "different-tenant"
    session.rows[(Organization, organization.id)] = organization

    with pytest.raises(DemoSeedConflictError, match="already in use"):
        await seed_demo_identity(session)

@pytest.mark.asyncio
async def test_demo_seed_rejects_inactive_organization_without_reactivating_it():
    session = MemorySession()
    organization, user = build_demo_records()
    organization.is_active = False
    user.is_active = True
    session.rows[(Organization, organization.id)] = organization
    session.rows[(User, user.id)] = user

    with pytest.raises(DemoSeedConflictError, match="organization ID"):
        await seed_demo_identity(session)
    assert organization.is_active is False


@pytest.mark.asyncio
async def test_demo_seed_rejects_inactive_user_without_reactivating_it():
    session = MemorySession()
    organization, user = build_demo_records()
    organization.is_active = True
    user.is_active = False
    session.rows[(Organization, organization.id)] = organization
    session.rows[(User, user.id)] = user

    with pytest.raises(DemoSeedConflictError, match="user ID"):
        await seed_demo_identity(session)
    assert user.is_active is False
