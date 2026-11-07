"""Offline retrieval statement and citation-boundary regressions."""
from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest
from sqlalchemy import Text, select
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.dialects.postgresql.asyncpg import dialect as asyncpg_dialect

from app.api.v1.endpoints.documents import _visible_document_predicate
from app.core.demo_identity import build_demo_actor
from app.models import Document
from app.services.ingestion.embedding import FakeEmbedder
from app.services.retrieval.service import RetrievalService, build_authorized_statement


ORG = UUID("00000000-0000-4000-8000-000000000032")
DOC = UUID("00000000-0000-4000-8000-000000000101")
CHUNK = UUID("00000000-0000-4000-8000-000000000102")
OTHER_DOC = UUID("00000000-0000-4000-8000-000000000201")


def test_retrieval_statement_pushes_tenant_role_state_and_model_filters_before_top_k():
    actor = build_demo_actor()
    statement = build_authorized_statement(
        actor, "fake-minilm", "deterministic-v1", [0.0] * 384, 5
    )
    compiled = statement.compile(dialect=asyncpg_dialect())
    sql = compiled.string
    assert "embeddings.org_id =" in sql
    assert "documents.org_id =" in sql
    assert "documents.allowed_roles" in sql
    assert "documents.status =" in sql
    assert "documents.is_deleted IS false" in sql
    assert "embeddings.is_active IS true" in sql
    assert "embeddings.model_name =" in sql
    assert "embeddings.model_revision =" in sql
    assert sql.index("WHERE") < sql.index("ORDER BY") < sql.index("LIMIT")
    assert statement._limit_clause.value == 5


class FakeRows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeSession:
    def __init__(self, rows):
        self.rows = rows
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return FakeRows(self.rows)


class FixedEmbedder:
    model_name = "fake-minilm"
    model_revision = "deterministic-v1"

    def embed_texts(self, texts):
        return [[1.0] + [0.0] * 383 for _ in texts]


def _row(*, doc_id=DOC, org_id=ORG, roles=None, status="complete", deleted=False, active=True, score=0.9, index=0):
    document = SimpleNamespace(
        id=doc_id,
        org_id=org_id,
        status=status,
        is_deleted=deleted,
        allowed_roles=roles if roles is not None else ["employee"],
        title="Handbook",
    )
    chunk = SimpleNamespace(
        id=CHUNK if doc_id == DOC else OTHER_DOC,
        document_id=doc_id,
        chunk_index=index,
        page=2,
        content="The policy says twenty days.",
    )
    embedding = SimpleNamespace(
        org_id=org_id,
        is_active=active,
        model_name="fake-minilm",
        model_revision="deterministic-v1",
    )
    return embedding, chunk, document, score


@pytest.mark.asyncio
async def test_retrieval_returns_only_currently_permitted_ranked_canonical_evidence():
    session = FakeSession(
        [
            _row(score=0.9),
            _row(score=0.2, index=1),
            _row(doc_id=OTHER_DOC, org_id=UUID("00000000-0000-4000-8000-000000000777"), index=2),
            _row(doc_id=OTHER_DOC, roles=["superadmin"], index=3),
            _row(doc_id=OTHER_DOC, status="failed", index=4),
            _row(doc_id=OTHER_DOC, deleted=True, index=5),
            _row(doc_id=OTHER_DOC, active=False, index=6),
        ]
    )
    service = RetrievalService(FixedEmbedder(), minimum_similarity=0.35)
    evidence = await service.retrieve(session, build_demo_actor(), "leave days?", 5)

    assert len(evidence) == 1
    assert evidence[0].citation_id == 1
    assert evidence[0].chunk_id == CHUNK
    assert evidence[0].document_id == DOC
    assert evidence[0].page == 2
    assert evidence[0].similarity_score == 0.9
    assert "allowed_roles" in str(session.statement)


@pytest.mark.asyncio
async def test_weak_or_absent_rows_do_not_produce_evidence():
    session = FakeSession([_row(score=0.34)])
    service = RetrievalService(FixedEmbedder(), minimum_similarity=0.35)
    assert await service.retrieve(session, build_demo_actor(), "unrelated?", 5) == []


def test_retrieval_rejects_wrong_embedding_dimensions():
    with pytest.raises(ValueError, match="exactly 384"):
        build_authorized_statement(
            build_demo_actor(), "m", "r", [0.0] * 383, 5
        )


def _role_overlap_expression(statement):
    return next(
        clause
        for clause in statement.whereclause.clauses
        if getattr(getattr(clause, "operator", None), "opstring", None) == "?|"
    )


def test_retrieval_role_filter_uses_text_array_on_asyncpg():
    statement = build_authorized_statement(
        build_demo_actor(), "fake-minilm", "deterministic-v1", [0.0] * 384, 5
    )
    expression = _role_overlap_expression(statement)
    assert isinstance(expression.right.type, ARRAY)
    assert isinstance(expression.right.type.item_type, Text)
    compiled = statement.compile(dialect=asyncpg_dialect())
    assert "?| ARRAY[" in compiled.string
    assert "::JSONB" not in compiled.string


def test_document_list_role_filter_uses_text_array_on_asyncpg():
    actor = build_demo_actor()
    statement = select(Document.id).where(*_visible_document_predicate(actor))
    expression = _role_overlap_expression(statement)
    assert isinstance(expression.right.type, ARRAY)
    assert isinstance(expression.right.type.item_type, Text)
    compiled = statement.compile(dialect=asyncpg_dialect())
    assert "?| ARRAY[" in compiled.string
    assert "::JSONB" not in compiled.string


@pytest.mark.asyncio
async def test_retrieval_evidence_preserves_source_casing_accents_and_punctuation():
    text = "US policy: API key AbC123 is case-sensitive. Cafe" + chr(0x0301) + " costs " + chr(0x20AC) + "20!"
    session = FakeSession([_row(score=0.9)])
    session.rows[0][1].content = text
    service = RetrievalService(FixedEmbedder(), minimum_similarity=0.35)
    evidence = await service.retrieve(session, build_demo_actor(), "question?", 5)
    assert evidence[0].content == text

@pytest.mark.asyncio
async def test_retrieval_excludes_chunks_from_different_model():
    """A MiniLM-tagged chunk is never scored against a Google query vector."""
    class GoogleQueryEmbedder:
        model_name = "models/gemini-embedding-001"
        model_revision = "001"

        def embed_texts(self, texts):
            return [[1.0] + [0.0] * 383 for _ in texts]

    actor = build_demo_actor()
    # 1. SQL statement explicitly pushes model_name and model_revision equality predicates
    statement = build_authorized_statement(
        actor, GoogleQueryEmbedder.model_name, GoogleQueryEmbedder.model_revision, [0.0] * 384, 5
    )
    compiled = statement.compile(dialect=asyncpg_dialect())
    sql = compiled.string
    assert "embeddings.model_name =" in sql
    assert "embeddings.model_revision =" in sql

    # 2. Defense-in-depth: if a MiniLM row somehow reached post-filtering, it is dropped
    minilm_row = _row(score=0.95)
    minilm_row[0].model_name = "sentence-transformers/all-MiniLM-L6-v2"
    minilm_row[0].model_revision = "main"

    session = FakeSession([minilm_row])
    service = RetrievalService(GoogleQueryEmbedder(), minimum_similarity=0.35)
    evidence = await service.retrieve(session, actor, "question?", 5)
    # The MiniLM chunk is excluded fail-closed
    assert evidence == []


@pytest.mark.asyncio
async def test_retrieval_excludes_untagged_chunks_defense_in_depth():
    """Untagged chunks without model_name (forbidden by DB NOT NULL constraint) are excluded fail-closed as defense-in-depth."""
    actor = build_demo_actor()
    service = RetrievalService(FixedEmbedder(), minimum_similarity=0.35)

    # Case A: model_name is None
    row_none = _row(score=0.9)
    row_none[0].model_name = None
    session_none = FakeSession([row_none])
    evidence_none = await service.retrieve(session_none, actor, "question?", 5)
    assert evidence_none == []

    # Case B: model_name is empty string
    row_empty = _row(score=0.9)
    row_empty[0].model_name = ""
    session_empty = FakeSession([row_empty])
    evidence_empty = await service.retrieve(session_empty, actor, "question?", 5)
    assert evidence_empty == []


@pytest.mark.asyncio
async def test_retrieval_clamps_similarity_score_to_contract_range():
    """Cosine similarity derived from pgvector distance is strictly clamped to [-1.0, 1.0]."""
    actor = build_demo_actor()
    service = RetrievalService(FixedEmbedder(), minimum_similarity=-1.0)

    # Scores > 1.0 or < -1.0 must be clamped to [-1.0, 1.0]
    row_overflow = _row(score=1.05)
    session = FakeSession([row_overflow])
    evidence = await service.retrieve(session, actor, "question?", 5)
    assert len(evidence) == 1
    assert evidence[0].similarity_score == 1.0

    row_underflow = _row(score=-1.20)
    session_under = FakeSession([row_underflow])
    evidence_under = await service.retrieve(session_under, actor, "question?", 5)
    assert len(evidence_under) == 1
    assert evidence_under[0].similarity_score == -1.0


@pytest.mark.asyncio
async def test_retrieval_canonicalizes_embedding_model_names_across_prefix_variants():
    """Ingest under 'models/gemini-embedding-001' and query under 'gemini-embedding-001'.

    The SQL predicate and post-filter must use the same canonical tag ('gemini-embedding-001')
    so stored chunks are found regardless of 'models/' prefix spelling. Existing MiniLM rows
    are unaffected.
    """
    from app.core.config import canonicalize_embedding_model_name
    from app.services.ingestion.embedding import GoogleGenAIEmbedder

    # 1. Verify canonicalization function behavior directly
    assert canonicalize_embedding_model_name("models/gemini-embedding-001") == "gemini-embedding-001"
    assert canonicalize_embedding_model_name("gemini-embedding-001") == "gemini-embedding-001"
    # Existing MiniLM rows are unaffected
    assert (
        canonicalize_embedding_model_name("sentence-transformers/all-MiniLM-L6-v2")
        == "sentence-transformers/all-MiniLM-L6-v2"
    )

    actor = build_demo_actor()

    # 2. Ingested under "models/gemini-embedding-001": GoogleGenAIEmbedder normalizes tag at construction
    ingest_embedder = GoogleGenAIEmbedder(
        model_name="models/gemini-embedding-001",
        model_revision="001",
    )
    assert ingest_embedder.model_name == "gemini-embedding-001"

    # Simulated stored chunk in DB has the canonical tag
    stored_row = _row(score=0.92)
    stored_row[0].model_name = ingest_embedder.model_name  # "gemini-embedding-001"
    stored_row[0].model_revision = "001"

    # 3. Query under "gemini-embedding-001" (unprefixed)
    class QueryEmbedder:
        model_name = "gemini-embedding-001"
        model_revision = "001"

        def embed_texts(self, texts, *, task_type=None):
            return [[0.1] * 384 for _ in texts]

    # Verify SQL predicate uses the canonical tag
    stmt = build_authorized_statement(
        actor, QueryEmbedder.model_name, QueryEmbedder.model_revision, [0.1] * 384, 5
    )
    compiled_sql = str(stmt.compile(dialect=asyncpg_dialect()))
    assert "embeddings.model_name =" in compiled_sql

    session = FakeSession([stored_row])
    service = RetrievalService(QueryEmbedder(), minimum_similarity=0.35)
    evidence = await service.retrieve(session, actor, "test query?", 5)
    assert len(evidence) == 1
    assert evidence[0].chunk_id == stored_row[1].id

    # 4. Symmetrical case: Query under prefixed "models/gemini-embedding-001" finds canonical chunk
    class PrefixedQueryEmbedder:
        model_name = "models/gemini-embedding-001"
        model_revision = "001"

        def embed_texts(self, texts, *, task_type=None):
            return [[0.1] * 384 for _ in texts]

    stmt_prefixed = build_authorized_statement(
        actor, PrefixedQueryEmbedder.model_name, PrefixedQueryEmbedder.model_revision, [0.1] * 384, 5
    )
    # The statement canonicalizes model_name to "gemini-embedding-001"
    params = stmt_prefixed.compile(dialect=asyncpg_dialect()).params
    assert any(v == "gemini-embedding-001" for v in params.values())

    session_prefixed = FakeSession([stored_row])
    service_prefixed = RetrievalService(PrefixedQueryEmbedder(), minimum_similarity=0.35)
    evidence_prefixed = await service_prefixed.retrieve(session_prefixed, actor, "test query?", 5)
    assert len(evidence_prefixed) == 1
    assert evidence_prefixed[0].chunk_id == stored_row[1].id
