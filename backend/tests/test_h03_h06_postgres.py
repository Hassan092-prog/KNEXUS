"""Disposable PostgreSQL integration coverage for KNEXUS H03-H06."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
from types import SimpleNamespace
import os
import re
import threading
from urllib.parse import urlsplit
from uuid import UUID, uuid4, uuid5

import pytest
import pytest_asyncio
from docx import Document as WordDocument
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.api.dependencies import get_current_actor, get_generation_service, get_retrieval_service
from app.core.database import get_db
from app.models import Document, DocumentChunk, Embedding, IngestionJob, Organization, User, VECTOR_DIMENSIONS
from app.schemas import ActorContext, GenerationResult
from app.services.generation.errors import GenerationConfigurationError, MalformedOutputError, ProviderTimeoutError, ProviderUnavailableError
from app.services.ingestion.embedding import FakeEmbedder
from app.services.ingestion.parsing import ParsedSection, parse_document_bytes
from app.services.retrieval.service import RetrievalService

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def _guard_database_url():
    url = os.environ.get("DATABASE_URL")
    expected = os.environ.get("KNEXUS_VERIFY_EXPECTED_DATABASE_URL")
    if not url or url != expected:
        raise AssertionError("DATABASE_URL does not match KNEXUS_VERIFY_EXPECTED_DATABASE_URL")
    parsed = urlsplit(url)
    if parsed.scheme != "postgresql+asyncpg":
        raise AssertionError(f"Expected postgresql+asyncpg, got {parsed.scheme}")
    if parsed.hostname != "127.0.0.1":
        raise AssertionError(f"Loopback target required (127.0.0.1), got {parsed.hostname}")
    if parsed.path == "/knexus" and parsed.port == 5435 and parsed.username == "knexus_admin":
        raise AssertionError("Guarded check rejected target: points to shared development database!")
    assert parsed.username == os.environ.get("POSTGRES_USER")
    assert parsed.password == os.environ.get("POSTGRES_PASSWORD")
    assert parsed.path == "/" + os.environ.get("POSTGRES_DB")
    assert parsed.port == int(os.environ.get("POSTGRES_PORT"))
    return url


def test_offline_harness_synthetic_identity_guard():
    """Exercise the harness target guard without creating an engine or connecting."""
    keys = ("DATABASE_URL", "KNEXUS_VERIFY_EXPECTED_DATABASE_URL", "POSTGRES_DB",
            "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_PORT")
    old = {key: os.environ.get(key) for key in keys}
    try:
        target = "postgresql+asyncpg://synthetic:synthetic@127.0.0.1:1/knx_offline"
        os.environ.update({
            "DATABASE_URL": target, "KNEXUS_VERIFY_EXPECTED_DATABASE_URL": target,
            "POSTGRES_DB": "knx_offline", "POSTGRES_USER": "synthetic",
            "POSTGRES_PASSWORD": "synthetic", "POSTGRES_PORT": "1",
        })
        assert _guard_database_url().endswith("/knx_offline")
        os.environ["DATABASE_URL"] = target.rsplit("/", 1)[0] + "/wrong"
        with pytest.raises(AssertionError):
            _guard_database_url()
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

def _dbapi_error_details(dbapi_error):
    # In handle_error, context.original_exception is the emulated DBAPI wrapper.
    # The wrapper directly carries SQLSTATE (as .sqlstate / .pgcode).
    # Its native driver error is reached via driver_exception or orig.
    sqlstate = getattr(dbapi_error, "sqlstate", None)
    native = getattr(dbapi_error, "driver_exception", None)
    if native is None:
        native = getattr(dbapi_error, "orig", None)
    if native is None:
        raise AssertionError("DBAPI adapter error did not expose native driver exception")
    return sqlstate, getattr(native, "constraint_name", None)


def test_offline_harness_dbapi_adapter_error_details():
    from sqlalchemy.dialects.postgresql.asyncpg import AsyncAdapt_asyncpg_dbapi

    native = SimpleNamespace(sqlstate="23503", constraint_name="fk_documents_uploader_same_org")
    wrapper = AsyncAdapt_asyncpg_dbapi.IntegrityError("synthetic FK violation", native)
    assert _dbapi_error_details(wrapper) == ("23503", "fk_documents_uploader_same_org")

    class FallbackWrapper(Exception):
        def __init__(self, driver):
            super().__init__("synthetic fallback")
            self.orig = driver
            self.sqlstate = driver.sqlstate

    fallback = FallbackWrapper(native)
    assert _dbapi_error_details(fallback) == ("23503", "fk_documents_uploader_same_org")

    with pytest.raises(AssertionError, match="did not expose native driver exception"):
        _dbapi_error_details(Exception("raw unlinked error"))



@pytest_asyncio.fixture
async def pg_engine():
    if os.environ.get("KNEXUS_ENABLE_DISPOSABLE_PG_TESTS") not in ("1", "true", "TRUE", "yes", "YES"):
        pytest.skip("Disposable PostgreSQL test skipped; set KNEXUS_ENABLE_DISPOSABLE_PG_TESTS=1 to run against an isolated target")
    engine = create_async_engine(_guard_database_url(), poolclass=NullPool)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def pg_sessions(pg_engine):
    yield async_sessionmaker(pg_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def api(pg_sessions, monkeypatch, tmp_path):
    from app.main import app
    from app.api.v1.endpoints import documents as document_routes

    state = {
        "actor": None,
        "retrieval": RetrievalService(FakeEmbedder(), minimum_similarity=-1.0),
        "generator": None,
    }
    background = []

    async def db_override():
        async with pg_sessions() as session:
            yield session

    async def capture_background(document_id, **kwargs):
        background.append((document_id, kwargs))

    monkeypatch.setattr(document_routes, "process_document", capture_background)
    monkeypatch.setattr(
        __import__("app.core.config", fromlist=["settings"]).settings,
        "DOCUMENT_STORAGE_ROOT", tmp_path / "private-uploads",
    )
    app.dependency_overrides[get_db] = db_override
    app.dependency_overrides[get_current_actor] = lambda: state["actor"]
    app.dependency_overrides[get_retrieval_service] = lambda: state["retrieval"]
    app.dependency_overrides[get_generation_service] = lambda: state["generator"]
    client = AsyncClient(transport=ASGITransport(app=app), base_url="http://knexus.test")
    try:
        yield client, state, background, tmp_path / "private-uploads"
    finally:
        await client.aclose()
        app.dependency_overrides.clear()


class EchoGenerator:
    provider = "fake"
    model = "deterministic-test"

    def __init__(self):
        self.requests = []

    async def generate(self, request):
        self.requests.append(request)
        item = request.evidence[0]
        return GenerationResult(
            answer=f"Supported by the supplied source [{item.citation_id}]",
            cited_ids=[item.citation_id], abstained=False, abstention_reason=None,
        )


class RaisingGenerator:
    provider = "fake"
    model = "deterministic-test"

    def __init__(self, exception):
        self.exception, self.requests = exception, []

    async def generate(self, request):
        self.requests.append(request)
        raise self.exception


class WordTokenizer:
    model_max_length = 512

    def encode(self, text, *, add_special_tokens=False):
        words = re.findall(r"\S+", text)
        return words + (["<S>", "</S>"] if add_special_tokens else [])

    def num_special_tokens_to_add(self, pair=False):
        return 2


class GateEmbedder(FakeEmbedder):
    def __init__(self):
        self.entered, self.release = threading.Event(), threading.Event()

    def embed_texts(self, texts):
        self.entered.set()
        if not self.release.wait(15):
            raise TimeoutError("offline test gate expired")
        return super().embed_texts(texts)


class BrokenEmbedder(FakeEmbedder):
    def embed_texts(self, texts):
        raise RuntimeError("synthetic fake provider failure")


class AxisEmbedder:
    model_name = "fake-minilm"
    model_revision = "deterministic-v1"

    def embed_texts(self, texts):
        return [[1.0] + [0.0] * 383 for _ in texts]


def _unit_vector(x, y=0.0):
    norm = (x * x + y * y) ** 0.5
    return [x / norm, y / norm] + [0.0] * (VECTOR_DIMENSIONS - 2)


def _docx(paragraphs):
    document = WordDocument()
    for paragraph in paragraphs:
        document.add_paragraph(paragraph)
    stream = BytesIO()
    document.save(stream)
    return stream.getvalue()


async def _tenant(sessions):
    suffix = uuid4().hex
    org = Organization(id=uuid4(), name="Synthetic verification organization",
                       slug="knx-h03-" + suffix, is_active=True)
    async with sessions() as session:
        session.add(org)
        await session.flush()
        user = User(id=uuid4(), org_id=org.id, email=f"{suffix}@example.invalid",
                    full_name="Synthetic actor", role="employee",
                    is_active=True, is_demo=False)
        session.add(user)
        await session.flush()
        await session.commit()
    return org.id, user.id


async def _additional_user_in_org(sessions, org_id):
    suffix = uuid4().hex
    user = User(id=uuid4(), org_id=org_id, email=f"uploader-{suffix}@example.invalid",
                full_name="Synthetic uploader", role="employee",
                is_active=True, is_demo=False)
    async with sessions() as session:
        session.add(user)
        await session.flush()
        await session.commit()
    return user.id


class _MemoryFixtureSession:
    def __init__(self, rows):
        self.rows = rows

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return False

    def add(self, row):
        self.rows.append(row)

    async def flush(self):
        return None

    async def commit(self):
        return None


class _MemoryFixtureSessions:
    def __init__(self):
        self.rows = []

    def __call__(self):
        return _MemoryFixtureSession(self.rows)


@pytest.mark.asyncio
async def test_offline_authorization_fixture_relationships():
    sessions = _MemoryFixtureSessions()
    org_id, actor_user_id = await _tenant(sessions)
    uploader_user_id = await _additional_user_in_org(sessions, org_id)
    foreign_org_id, foreign_user_id = await _tenant(sessions)

    users = {row.id: row for row in sessions.rows if isinstance(row, User)}
    assert actor_user_id != uploader_user_id
    assert users[actor_user_id].org_id == org_id
    assert users[uploader_user_id].org_id == org_id
    assert foreign_org_id != org_id
    assert users[foreign_user_id].org_id == foreign_org_id


def _actor(org_id, user_id, roles=("employee",)):
    return ActorContext(org_id=org_id, user_id=user_id, effective_roles=list(roles))


async def _insert_doc(session, *, org_id, user_id, title, roles, content,
                      vector=None, created_at=None, include_job=False):
    doc_id, chunk_id = uuid4(), uuid4()
    doc = Document(
        id=doc_id, org_id=org_id, uploaded_by=user_id, title=title,
        source_type="docx", original_filename=title + ".docx", storage_key=None,
        file_size_bytes=256, allowed_roles=roles, status="complete", chunk_count=1,
        description=None, metadata_json={"verification": "synthetic"},
        is_deleted=False, created_at=created_at or datetime.now(timezone.utc),
    )
    session.add(doc)
    await session.flush()
    chunk = DocumentChunk(
        id=chunk_id, org_id=org_id, document_id=doc_id, chunk_index=0,
        content=content, page=1, token_count=len(content.split()),
        source_metadata={"section": "synthetic"},
    )
    session.add(chunk)
    await session.flush()
    if vector is not None:
        session.add(Embedding(
            org_id=org_id, document_id=doc_id, chunk_id=chunk_id,
            embedding=vector, model_name="fake-minilm",
            model_revision="deterministic-v1", is_active=True,
        ))
        await session.flush()
    if include_job:
        now = datetime.now(timezone.utc)
        session.add(IngestionJob(
            org_id=org_id, document_id=doc_id, attempt_number=1, status="complete",
            chunks_processed=1, total_chunks=1,
            started_at=now - timedelta(seconds=1), finished_at=now,
        ))
        await session.flush()
    return doc, chunk


async def _upload(client, data, title="Synthetic handbook"):
    return await client.post(
        "/api/v1/documents/upload",
        files=[
            ("file", ("handbook.docx", data, DOCX_MIME)),
            ("allowed_roles", (None, "employee")),
            ("title", (None, title)),
            ("description", (None, "Disposable integration fixture")),
        ],
    )


async def _accepted(api_fixture, sessions, paragraphs):
    client, state, background, storage = api_fixture
    org_id, user_id = await _tenant(sessions)
    state["actor"] = _actor(org_id, user_id)
    source = _docx(paragraphs)
    response = await _upload(client, source)
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "queued" and len(background) == 1
    async with sessions() as session:
        doc = await session.get(Document, UUID(body["document_id"]))
        job = await session.get(IngestionJob, UUID(body["task_id"]))
        assert doc.status == "queued" and job.status == "queued"
        assert job.chunks_processed == 0 and job.total_chunks is None
    path = storage / doc.storage_key
    assert path.is_file()
    return body, source, path, org_id, user_id


async def _attempts(sessions, document_id):
    async with sessions() as session:
        result = await session.execute(
            select(IngestionJob).where(IngestionJob.document_id == document_id)
            .order_by(IngestionJob.attempt_number)
        )
        return result.scalars().all()


@pytest.mark.asyncio
async def test_explicit_demo_seed_persists_once_across_fresh_sessions(pg_sessions):
    from app.core.demo_identity import build_demo_actor
    from app.db.demo_seed import seed_demo_identity

    expected = build_demo_actor()
    async with pg_sessions() as session:
        assert await seed_demo_identity(session) == expected
        await session.commit()
    async with pg_sessions() as session:
        assert await seed_demo_identity(session) == expected
        await session.commit()
    async with pg_sessions() as session:
        orgs = await session.scalar(select(func.count()).select_from(Organization)
                                    .where(Organization.id == expected.org_id))
        users = await session.scalar(select(func.count()).select_from(User)
                                     .where(User.id == expected.user_id))
        org, user = await session.get(Organization, expected.org_id), await session.get(User, expected.user_id)
    assert orgs == users == 1
    assert org.is_active and user.is_active and user.is_demo


@pytest.mark.asyncio
async def test_upload_processing_preserves_source_and_query_citation(api, pg_sessions):
    from app.services.ingestion.processor import process_document

    client, state, _, _ = api
    generator = EchoGenerator()
    state["generator"] = generator
    p1 = "AbC123 US Caf\u00e9, e.g.; punctuation! " + "alpha " * 248
    p2 = "SectionTwo starts here: Zaid's US policy? " + "beta " * 120
    body, raw, stored_path, org_id, user_id = await _accepted(api, pg_sessions, [p1, p2])
    doc_id, job_id = UUID(body["document_id"]), UUID(body["task_id"])
    sections = parse_document_bytes(raw, "docx")
    assert len(sections) == 2
    source_text = "\n\n".join(section.text for section in sections)

    gate = GateEmbedder()
    processing = __import__("asyncio").create_task(process_document(
        doc_id, session_factory=pg_sessions, embedder=gate, tokenizer=WordTokenizer()
    ))
    try:
        assert await __import__("asyncio").to_thread(gate.entered.wait, 10)
        async with pg_sessions() as session:
            doc, job = await session.get(Document, doc_id), await session.get(IngestionJob, job_id)
            assert doc.status == job.status == "processing"
            assert job.started_at is not None and job.finished_at is None
    finally:
        gate.release.set()
    assert await __import__("asyncio").wait_for(processing, timeout=20) is True

    async with pg_sessions() as session:
        doc, job = await session.get(Document, doc_id), await session.get(IngestionJob, job_id)
        chunks = (await session.execute(
            select(DocumentChunk).where(DocumentChunk.document_id == doc_id)
            .order_by(DocumentChunk.chunk_index)
        )).scalars().all()
        embeddings = (await session.execute(
            select(Embedding).where(Embedding.document_id == doc_id)
        )).scalars().all()
        assert doc.status == job.status == "complete"
        assert doc.chunk_count == job.chunks_processed == job.total_chunks == len(chunks)
        assert job.finished_at is not None and job.failure_code is job.failure_message is None
    assert len(chunks) >= 2 and len(embeddings) == len(chunks)
    assert [chunk.chunk_index for chunk in chunks] == list(range(len(chunks)))
    assert [chunk.id for chunk in chunks] == [
        uuid5(doc_id, f"chunk:{index}") for index in range(len(chunks))
    ]
    assert any(len(chunk.source_metadata["sections"]) >= 2 for chunk in chunks)
    for chunk in chunks:
        start, end = chunk.source_metadata["char_start"], chunk.source_metadata["char_end"]
        assert source_text[start:end] == chunk.content
        assert 0 < chunk.token_count <= 240
        assert chunk.source_metadata["sections"]
    assert len({chunk.id for chunk in chunks}) == len(chunks)
    all_text = "\n".join(chunk.content for chunk in chunks)
    assert "AbC123" in all_text and "US" in all_text
    assert "Caf\u00e9, e.g.; punctuation!" in all_text
    assert "SectionTwo starts here: Zaid's US policy?" in all_text
    assert stored_path.is_file()
    assert all(len(row.embedding) == VECTOR_DIMENSIONS == 384 for row in embeddings)
    assert all(row.model_name == gate.model_name and row.model_revision == gate.model_revision
               for row in embeddings)

    state["retrieval"] = RetrievalService(gate, minimum_similarity=-1.0)
    answer = await client.post(
        "/api/v1/query",
        json={"question": "Where is the supplied policy?", "top_k": 5, "stream": False},
    )
    assert answer.status_code == 200, answer.text
    result = answer.json()
    assert result["abstained"] is False and result["citations"]
    cited = result["citations"][0]
    matching = next(chunk for chunk in chunks if str(chunk.id) == cited["chunk_id"])
    assert cited["document_id"] == str(doc_id) and cited["excerpt"] == matching.content
    assert generator.requests and generator.requests[0].evidence


@pytest.mark.asyncio
async def test_postgresql_role_and_tenant_filters_precede_document_pagination_and_status(api, pg_sessions):
    client, state, _, _ = api
    org, actor_user = await _tenant(pg_sessions)
    uploader = await _additional_user_in_org(pg_sessions, org)
    foreign_org, foreign_user = await _tenant(pg_sessions)
    state["actor"] = _actor(org, actor_user)
    now = datetime.now(timezone.utc)
    async with pg_sessions() as session:
        older, _ = await _insert_doc(session, org_id=org, user_id=uploader,
            title="visible-older", roles=["employee"], content="Visible older.",
            created_at=now, include_job=True)
        newer, _ = await _insert_doc(session, org_id=org, user_id=uploader,
            title="visible-newer", roles=["employee"], content="Visible newer.",
            created_at=now + timedelta(seconds=2), include_job=True)
        restricted, _ = await _insert_doc(session, org_id=org, user_id=uploader,
            title="manager-only", roles=["manager"], content="Restricted.",
            created_at=now + timedelta(seconds=3), include_job=True)
        foreign, _ = await _insert_doc(session, org_id=foreign_org, user_id=foreign_user,
            title="foreign-tenant", roles=["employee"], content="Foreign.",
            created_at=now + timedelta(seconds=4), include_job=True)
        await session.commit()
    page = await client.get("/api/v1/documents?limit=1&offset=1")
    assert page.status_code == 200, page.text
    assert page.json()["meta"] == {"total": 2, "limit": 1, "offset": 1}
    assert [item["id"] for item in page.json()["data"]] == [str(older.id)]
    assert (await client.get(f"/api/v1/documents/{older.id}")).status_code == 200
    status = await client.get(f"/api/v1/documents/{older.id}/status")
    assert status.status_code == 403 and status.json()["code"] == "FORBIDDEN"
    denied_role = await client.get(f"/api/v1/documents/{restricted.id}")
    assert denied_role.status_code == 403 and denied_role.json()["code"] == "FORBIDDEN"
    denied_tenant = await client.get(f"/api/v1/documents/{foreign.id}")
    assert denied_tenant.status_code == 404 and denied_tenant.json()["code"] == "NOT_FOUND"
    state["actor"] = _actor(org, actor_user, ("orgadmin", "manager", "employee"))
    admin_status = await client.get(f"/api/v1/documents/{older.id}/status")
    assert admin_status.status_code == 200
    assert admin_status.json()["status"] == "complete"
    assert admin_status.json()["progress_percent"] == 100
    assert newer.id != older.id


@pytest.mark.asyncio
async def test_postgresql_retrieval_role_and_tenant_filters_before_top_k(pg_sessions):
    org, user = await _tenant(pg_sessions)
    other_org, other_user = await _tenant(pg_sessions)
    actor = _actor(org, user)
    async with pg_sessions() as session:
        denied, _ = await _insert_doc(session, org_id=org, user_id=user,
            title="restricted-nearest", roles=["manager"], content="Restricted nearest.",
            vector=_unit_vector(1.0))
        foreign, _ = await _insert_doc(session, org_id=other_org, user_id=other_user,
            title="foreign-nearest", roles=["employee"], content="Foreign nearest.",
            vector=_unit_vector(1.0))
        allowed, _ = await _insert_doc(session, org_id=org, user_id=user,
            title="allowed-next", roles=["employee"], content="Allowed evidence.",
            vector=_unit_vector(0.8, 0.6))
        await _insert_doc(session, org_id=org, user_id=user,
            title="allowed-farther", roles=["employee"], content="Farther evidence.",
            vector=_unit_vector(0.2, 0.98))
        await session.commit()
        service = RetrievalService(AxisEmbedder(), minimum_similarity=-1.0)
        evidence = await service.retrieve(session, actor, "synthetic query", top_k=1)
    assert len(evidence) == 1
    assert evidence[0].document_id == allowed.id
    assert evidence[0].content == "Allowed evidence."
    assert evidence[0].document_id not in {denied.id, foreign.id}


@pytest.mark.asyncio
async def test_weak_evidence_returns_abstention_without_generation(api, pg_sessions):
    client, state, _, _ = api
    org, user = await _tenant(pg_sessions)
    state["actor"] = _actor(org, user)
    async with pg_sessions() as session:
        await _insert_doc(session, org_id=org, user_id=user, title="weak",
            roles=["employee"], content="Orthogonal weak evidence.",
            vector=_unit_vector(0.0, 1.0))
        await session.commit()
    generator = EchoGenerator()
    state["generator"] = generator
    state["retrieval"] = RetrievalService(AxisEmbedder(), minimum_similarity=0.9)
    result = await client.post("/api/v1/query",
        json={"question": "synthetic query", "top_k": 5, "stream": False})
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["abstained"] is True and body["answer"] is None
    assert body["citations"] == [] and body["abstention_reason"]
    assert generator.requests == []


@pytest.mark.asyncio
async def test_no_evidence_returns_abstention_without_generation(api, pg_sessions):
    client, state, _, _ = api
    org, user = await _tenant(pg_sessions)
    state["actor"] = _actor(org, user)
    generator = EchoGenerator()
    state["generator"] = generator
    state["retrieval"] = RetrievalService(AxisEmbedder(), minimum_similarity=0.5)
    response = await client.post(
        "/api/v1/query",
        json={"question": "question with no indexed evidence", "top_k": 3, "stream": False},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["abstained"] is True and body["answer"] is None
    assert body["citations"] == [] and body["abstention_reason"]
    assert generator.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error_type", "status", "code"),
    [
        (ProviderUnavailableError, 503, "PROVIDER_UNAVAILABLE"),
        (GenerationConfigurationError, 503, "PROVIDER_UNAVAILABLE"),
        (ProviderTimeoutError, 504, "PROVIDER_UNAVAILABLE"),
        (MalformedOutputError, 502, "INVALID_CITATIONS"),
    ],
)
async def test_generation_failures_map_to_safe_contract_errors(api, pg_sessions, error_type, status, code):
    client, state, _, _ = api
    org, user = await _tenant(pg_sessions)
    state["actor"] = _actor(org, user)
    async with pg_sessions() as session:
        await _insert_doc(session, org_id=org, user_id=user, title="provider fixture",
            roles=["employee"], content="Provider error evidence.",
            vector=_unit_vector(1.0))
        await session.commit()
    failed = RaisingGenerator(error_type("synthetic provider failure"))
    state["generator"] = failed
    state["retrieval"] = RetrievalService(AxisEmbedder(), minimum_similarity=-1.0)
    response = await client.post("/api/v1/query",
        json={"question": "synthetic query", "top_k": 3, "stream": False})
    assert response.status_code == status
    assert response.json()["code"] == code
    assert response.json()["request_id"] == response.headers["x-request-id"]
    assert response.json()["detail"] and len(failed.requests) == 1


@pytest.mark.asyncio
async def test_processing_failure_retry_and_temporary_upload_cleanup(api, pg_sessions):
    from app.services.ingestion.processor import enqueue_document_retry, process_document

    client, _, _, storage = api
    body, _, path, org, user = await _accepted(
        api, pg_sessions, ["Retryable source AbC123. " + "word " * 30]
    )
    doc_id = UUID(body["document_id"])
    assert await process_document(doc_id, session_factory=pg_sessions,
        embedder=BrokenEmbedder(), tokenizer=WordTokenizer()) is False
    attempts = await _attempts(pg_sessions, doc_id)
    assert attempts[0].status == "failed"
    assert attempts[0].failure_code == "PROCESSING_FAILED"
    assert attempts[0].failure_message and attempts[0].failure_message.strip()
    assert attempts[0].finished_at is not None
    actor = _actor(org, user)
    async with pg_sessions() as session:
        retry = await enqueue_document_retry(session, actor, doc_id)
        assert retry.attempt_number == 2 and retry.status == "queued"
    assert await process_document(doc_id, session_factory=pg_sessions,
        embedder=FakeEmbedder(), tokenizer=WordTokenizer()) is True
    attempts = await _attempts(pg_sessions, doc_id)
    assert [(item.attempt_number, item.status) for item in attempts] == [
        (1, "failed"), (2, "complete")
    ]
    assert attempts[1].failure_code is None and attempts[1].failure_message is None
    assert path.is_file() and storage.is_dir()

    # A real tenant exists but the server actor's user does not. The named
    # composite FK must reject persistence; the route must delete its staged file.
    suffix = uuid4().hex
    org_row = Organization(id=uuid4(), name="Cleanup tenant",
        slug="knx-cleanup-" + suffix, is_active=True)
    async with pg_sessions() as session:
        session.add(org_row)
        await session.flush()
        await session.commit()
    from app.api.v1.endpoints import documents as document_routes
    from sqlalchemy import event as sqlalchemy_event
    api_client, state, _, storage_root = api
    state["actor"] = _actor(org_row.id, uuid4())
    observed = []

    def capture_db_error(context):
        observed.append(_dbapi_error_details(context.original_exception))

    existing_files = set(storage_root.iterdir())
    sync_engine = pg_sessions.kw["bind"].sync_engine
    sqlalchemy_event.listen(sync_engine, "handle_error", capture_db_error)
    try:
        failed_upload = await _upload(api_client, _docx(["Must clean failed upload."]))
    finally:
        sqlalchemy_event.remove(sync_engine, "handle_error", capture_db_error)
    assert failed_upload.status_code == 500
    assert failed_upload.json()["code"] == "INTERNAL_ERROR"
    assert ("23503", "fk_documents_uploader_same_org") in observed
    assert set(storage_root.iterdir()) == existing_files
    async with pg_sessions() as session:
        count = await session.scalar(select(func.count()).select_from(Document)
                                     .where(Document.org_id == org_row.id))
    assert count == 0


@pytest.mark.asyncio
async def test_confirmed_restart_recovers_abandoned_jobs_and_explicit_retry(pg_sessions):
    from app.services.ingestion.processor import (
        enqueue_document_retry, process_document, recover_interrupted_jobs,
    )

    org, user = await _tenant(pg_sessions)
    async with pg_sessions() as session:
        baseline = await session.scalar(
            select(func.count()).select_from(IngestionJob)
            .where(IngestionJob.status.in_(("queued", "processing")))
        )
        now = datetime.now(timezone.utc)
        queued_doc = Document(
            org_id=org, uploaded_by=user, title="abandoned queued",
            source_type="docx", original_filename="queued.docx", file_size_bytes=64,
            allowed_roles=["employee"], status="queued", chunk_count=0,
            metadata_json={}, is_deleted=False,
        )
        session.add(queued_doc)
        await session.flush()
        queued_job = IngestionJob(org_id=org, document_id=queued_doc.id,
            attempt_number=1, status="queued", chunks_processed=0)
        session.add(queued_job)
        await session.flush()
        processing_doc = Document(
            org_id=org, uploaded_by=user, title="abandoned processing",
            source_type="docx", original_filename="processing.docx", file_size_bytes=64,
            allowed_roles=["employee"], status="processing", chunk_count=0,
            metadata_json={}, is_deleted=False,
        )
        session.add(processing_doc)
        await session.flush()
        processing_job = IngestionJob(
            org_id=org, document_id=processing_doc.id, attempt_number=1,
            status="processing", chunks_processed=0, started_at=now,
        )
        session.add(processing_job)
        await session.flush()
        await session.commit()
        queued_id, processing_id = queued_doc.id, processing_doc.id
        queued_job_id, processing_job_id = queued_job.id, processing_job.id

    with pytest.raises(ValueError, match="workers are stopped"):
        await recover_interrupted_jobs(pg_sessions, workers_stopped=False)
    async with pg_sessions() as session:
        assert (await session.get(IngestionJob, queued_job_id)).status == "queued"
        assert (await session.get(IngestionJob, processing_job_id)).status == "processing"
    assert await recover_interrupted_jobs(pg_sessions, workers_stopped=True) == baseline + 2
    async with pg_sessions() as session:
        for job_id in (queued_job_id, processing_job_id):
            job = await session.get(IngestionJob, job_id)
            assert job.status == "failed" and job.failure_code == "INTERRUPTED"
            assert job.failure_message and job.failure_message.strip()
            assert job.finished_at is not None
        assert (await session.get(Document, queued_id)).status == "failed"
        assert (await session.get(Document, processing_id)).status == "failed"
    async with pg_sessions() as session:
        retry = await enqueue_document_retry(session, _actor(org, user), queued_id)
        assert retry.attempt_number == 2 and retry.status == "queued"
    recovered = [ParsedSection("Recovered after confirmed restart.", None, {"source": "synthetic"})]
    assert await process_document(queued_id, parsed_sections=recovered,
        session_factory=pg_sessions, embedder=FakeEmbedder(),
        tokenizer=WordTokenizer()) is True
    attempts = await _attempts(pg_sessions, queued_id)
    assert [(item.attempt_number, item.status) for item in attempts] == [
        (1, "failed"), (2, "complete")
    ]
