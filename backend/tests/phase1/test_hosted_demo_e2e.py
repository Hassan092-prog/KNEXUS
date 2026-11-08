"""Offline end-to-end test of the hosted demo path with the real API code.

Flow exercised through the real FastAPI routes and real ingestion/generation
code, with every outbound HTTP call served by ``httpx.MockTransport``:

  1. POST /api/v1/documents/upload of backend/tests/fixtures/demo/demo_security_policy.docx
  2. real ``process_document`` (parsing -> chunking -> hosted embedding) until
     the persisted status reaches ``complete``
  3. POST /api/v1/query with question q01 from the demo question set

Hosted configuration under test: EMBEDDING_PROVIDER=google
(gemini-embedding-001, 384-d output) and GENERATION_PROVIDER=groq
(openai/gpt-oss-120b). Persistence is an in-memory session seam (same pattern
as test_api_phase1.py); the retrieval statement built by the real
``build_authorized_statement`` is answered by the seam and then re-filtered by
the real RetrievalService logic. No real keys; no real network (socket spy);
no DB connection: documents.py's background task is stubbed (as in
test_api_phase1.py) and ``process_document`` is invoked through its published
keyword injection points (embedder/token_counter/session_factory).
"""
from __future__ import annotations

import asyncio
import json
import socket
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy.dialects.postgresql.asyncpg import dialect as asyncpg_dialect

from app.api.dependencies import (
    get_db,
    get_dispatch_policy,
    get_generation_quota_ledger,
    get_generation_transport,
    get_retrieval_service,
)
from app.core.config import canonicalize_embedding_model_name, settings
from app.core.demo_identity import build_demo_actor
from app.core.dispatch_policy import MockDispatchPolicy
from app.core.generation import GenerationResult
from app.core.quota import QuotaConfig, QuotaLedger
from app.core.token_counter import GoogleGenAITokenCounter
from app.main import app
from app.models import Document, DocumentChunk, Embedding, IngestionJob
from app.services.ingestion.embedding import GoogleGenAIEmbedder
from app.services.ingestion.processor import process_document
from app.services.retrieval.service import RetrievalService

DEMO_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "demo"
DEMO_DOCX = DEMO_DIR / "demo_security_policy.docx"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
WATCH_FACT = "Review Cycle: Annual"  # q01's expected_fact, verified chunk-survivable in test_demo_set
DEMO_ORG_ID = UUID("00000000-0000-4000-8000-000000000032")
EXPECTED_DIRECTION = 7   # direction of the chunk that answers q01 and of the query vector
UNRELATED_DIRECTION = 200


def _unit_vector(direction: int) -> list[float]:
    vector = [0.0] * 384
    vector[direction] = 1.0
    return vector


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm = (sum(x * x for x in a) ** 0.5) * (sum(y * y for y in b) ** 0.5)
    if norm == 0:
        return 0.0
    return max(-1.0, min(1.0, dot / norm))


class Result:
    def __init__(self, rows=()):
        self._rows = list(rows)

    def scalars(self):
        return self

    def all(self):
        return self._rows

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None


class DemoSession:
    """In-memory persistence seam shaped after test_api_phase1.FakeSession."""

    def __init__(self):
        self.documents: dict[UUID, Document] = {}
        self.jobs: dict[UUID, IngestionJob] = {}
        self.chunks: dict[UUID, DocumentChunk] = {}
        self.embeddings: list[Embedding] = []
        self.commits = 0

    def add(self, row):
        if isinstance(row, Document):
            self.documents[row.id] = row
        elif isinstance(row, IngestionJob):
            self.jobs[row.id] = row
        elif isinstance(row, DocumentChunk):
            self.chunks[row.id] = row
        elif isinstance(row, Embedding):
            self.embeddings.append(row)

    async def flush(self):
        return None

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, model, key):
        if model is Document:
            return self.documents.get(key)
        if model is DocumentChunk:
            return self.chunks.get(key)
        return None

    async def execute(self, statement):
        rendered = str(statement)
        if "embeddings" in rendered and self._query_vector(statement) is not None:
            return Result(self._retrieval_rows(statement))
        if "ingestion_jobs" in rendered:
            latest = sorted(
                self.jobs.values(), key=lambda job: job.attempt_number, reverse=True
            )[:1]
            return Result(latest)
        if "documents" in rendered:
            return Result(list(self.documents.values()))
        return Result()

    _compiled_cache: dict = {}

    def _query_vector(self, statement):
        try:
            compiled = statement.compile(dialect=asyncpg_dialect())
        except Exception:
            return None
        for value in compiled.params.values():
            if isinstance(value, list) and len(value) == 384:
                return value
        return None

    def _retrieval_rows(self, statement):
        """Stand in for Postgres/pgvector: coarse SQL predicates + cosine ranking.

        The real RetrievalService re-applies every predicate after this, so this
        seam only needs to emulate the SQL-level ranking honestly.
        """
        query_vector = self._query_vector(statement)
        limit = statement._limit_clause.value or 10
        actor = build_demo_actor()
        rows = []
        for embedding in self.embeddings:
            if not embedding.is_active:
                continue
            if canonicalize_embedding_model_name(embedding.model_name) != canonicalize_embedding_model_name(
                "gemini-embedding-001"
            ):
                continue
            chunk = self.chunks.get(embedding.chunk_id)
            document = self.documents.get(embedding.document_id)
            if chunk is None or document is None:
                continue
            if document.status != "complete" or document.is_deleted:
                continue
            if embedding.org_id != DEMO_ORG_ID or document.org_id != DEMO_ORG_ID:
                continue
            if not set(document.allowed_roles).intersection(actor.effective_roles):
                continue
            similarity = _cosine_similarity(query_vector, list(embedding.embedding))
            rows.append((embedding, chunk, document, similarity))
        rows.sort(key=lambda row: (-row[3], row[1].chunk_index))
        return rows[:limit]


@pytest.fixture()
def hosted_demo(monkeypatch, tmp_path: Path):
    # Socket spy (as in test_demo_set.py): every outbound HTTP call must flow
    # through the MockTransports; any attempt to actually open a network
    # connection hits socket.create_connection and fails the test immediately.
    # (Unlike the pure-chunking demo tests we cannot also patch
    # ``socket.socket.connect`` here: on Windows the TestClient portal's
    # loop self-pipe connect-retries on SO_ERROR and would deadlock startup.)
    def _no_socket(*args, **kwargs):  # pragma: no cover - defensive
        raise AssertionError("hosted demo e2e must not open real sockets")

    monkeypatch.setattr(socket, "create_connection", _no_socket)

    session = DemoSession()
    groq_mode = {"status": 200}
    google_requests: list[httpx.Request] = []
    google_bodies: list[dict] = []
    groq_requests: list[httpx.Request] = []

    async def override_db():
        yield session

    async def no_background_work(*args, **kwargs):  # documents.py background task stub
        return True

    from app.api.v1.endpoints import documents as document_routes

    monkeypatch.setattr(document_routes, "process_document", no_background_work)
    monkeypatch.setattr(settings, "DOCUMENT_STORAGE_ROOT", tmp_path / "private")
    monkeypatch.setattr(settings, "QUOTA_STATE_PATH", tmp_path / "quota_state.json")
    monkeypatch.setattr(settings, "QUOTA_CAMPAIGN_ID", "demo-hosted-e2e-campaign")
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "google")
    monkeypatch.setattr(settings, "EMBEDDING_MODEL_NAME", "gemini-embedding-001")
    monkeypatch.setattr(settings, "EMBEDDING_API_KEY", SecretStr("fake-google-demo-key"))
    monkeypatch.setattr(settings, "GENERATION_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GENERATION_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setattr(settings, "GENERATION_API_KEY", SecretStr("fake-groq-demo-key"))

    ledger = QuotaLedger(
        QuotaConfig(
            enabled=True,
            campaign_id="demo-hosted-e2e-campaign",
            max_campaign_attempts=500,
            max_requests_per_minute=1000,
            max_requests_per_day=10000,
            min_request_interval_seconds=0.0,
            state_path=tmp_path / "quota_state.json",
        )
    )

    def google_handler(request: httpx.Request) -> httpx.Response:
        google_requests.append(request)
        payload = json.loads(request.content.decode("utf-8"))
        google_bodies.append(payload)
        if ":countTokens" in str(request.url):
            text = payload["contents"][0]["parts"][0]["text"]
            return httpx.Response(200, json={"totalTokens": max(1, len(text) // 4)})
        embeddings = []
        for request_entry in payload["requests"]:
            if request_entry["taskType"] == "RETRIEVAL_QUERY":
                # The question vector must be closest to the expected chunk.
                embeddings.append({"values": _unit_vector(EXPECTED_DIRECTION)})
                continue
            text = request_entry["content"]["parts"][0]["text"]
            direction = EXPECTED_DIRECTION if WATCH_FACT in text else UNRELATED_DIRECTION
            embeddings.append({"values": _unit_vector(direction)})
        return httpx.Response(200, json={"embeddings": embeddings})

    def groq_handler(request: httpx.Request) -> httpx.Response:
        groq_requests.append(request)
        if groq_mode["status"] != 200:
            return httpx.Response(
                groq_mode["status"],
                json={"error": {"type": "unavailable", "message": "hosted groq outage"}},
            )
        result = GenerationResult(
            answer="According to the cited policy evidence the review is annual. " + WATCH_FACT + " [1].",
            cited_ids=[1],
            abstained=False,
            abstention_reason=None,
        )
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {"role": "assistant", "content": result.model_dump_json()},
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 50, "completion_tokens": 20, "total_tokens": 70},
            },
        )

    google_transport = httpx.MockTransport(google_handler)
    groq_transport = httpx.MockTransport(groq_handler)

    def build_embedder() -> GoogleGenAIEmbedder:
        return GoogleGenAIEmbedder(
            api_key="fake-google-demo-key",
            output_dimensions=384,
            transport=google_transport,
            dispatch_policy=MockDispatchPolicy(),
            quota_ledger=ledger,
        )

    def build_token_counter() -> GoogleGenAITokenCounter:
        return GoogleGenAITokenCounter(
            model_name="gemini-embedding-001",
            api_key="fake-google-demo-key",
            max_allowed_tokens=2048,
            transport=google_transport,
            dispatch_policy=MockDispatchPolicy(),
            quota_ledger=ledger,
        )

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_generation_quota_ledger] = lambda: ledger
    app.dependency_overrides[get_dispatch_policy] = lambda: MockDispatchPolicy("groq")
    app.dependency_overrides[get_generation_transport] = lambda: groq_transport
    app.dependency_overrides[get_retrieval_service] = lambda: RetrievalService(
        embedder=build_embedder(), token_counter=build_token_counter()
    )

    with TestClient(app) as client:
        yield SimpleNamespace(
            client=client,
            session=session,
            groq_mode=groq_mode,
            google_requests=google_requests,
            google_bodies=google_bodies,
            groq_requests=groq_requests,
            ledger=ledger,
            build_embedder=build_embedder,
            build_token_counter=build_token_counter,
        )
    app.dependency_overrides.clear()


def _upload_demo_policy(client: TestClient) -> httpx.Response:
    roles = json.loads((DEMO_DIR / "manifest.json").read_text(encoding="utf-8"))["documents"]
    allowed_roles = next(
        entry["allowed_roles"] for entry in roles if entry["filename"] == "demo_security_policy.docx"
    )
    return client.post(
        "/api/v1/documents/upload",
        files=[
            ("file", ("demo_security_policy.docx", DEMO_DOCX.read_bytes(), DOCX_MIME)),
            *[("allowed_roles", (None, role)) for role in allowed_roles],
            ("title", (None, "Enterprise Information Security Policy (demo)")),
        ],
    )


def _process_until_complete(hosted_demo, document_id: UUID) -> bool:
    return asyncio.run(
        process_document(
            document_id,
            session_factory=lambda: hosted_demo.session,
            embedder=hosted_demo.build_embedder(),
            token_counter=hosted_demo.build_token_counter(),
        )
    )


def test_hosted_demo_e2e_query_succeeds(hosted_demo) -> None:
    upload = _upload_demo_policy(hosted_demo.client)
    assert upload.status_code == 202
    document_id = UUID(upload.json()["document_id"])

    assert _process_until_complete(hosted_demo, document_id) is True

    status = hosted_demo.client.get(f"/api/v1/documents/{document_id}/status")
    assert status.status_code == 200
    assert status.json()["status"] == "complete"
    assert status.json()["progress_percent"] == 100

    questions = json.loads((DEMO_DIR / "questions.json").read_text(encoding="utf-8"))["questions"]
    q01 = next(question for question in questions if question["id"] == "demo_q01")
    query = hosted_demo.client.post(
        "/api/v1/query",
        json={"question": q01["question"], "top_k": 5, "stream": False},
    )
    assert query.status_code == 200
    body = query.json()
    assert body["abstained"] is False
    assert body["citations"], "expected citations for an answerable hosted demo question"
    assert all(citation["document_id"] == str(document_id) for citation in body["citations"])
    assert any(WATCH_FACT in citation["excerpt"] for citation in body["citations"])

    # Stored embeddings are tagged with the hosted model and carry 384 dims.
    assert hosted_demo.session.embeddings
    for embedding in hosted_demo.session.embeddings:
        assert embedding.model_name == "gemini-embedding-001"
        assert len(embedding.embedding) == 384

    # Google mock: ingestion used RETRIEVAL_DOCUMENT and the question RETRIEVAL_QUERY,
    # both with outputDimensionality 384; countTokens was exercised too.
    embed_entries = [
        request_entry
        for payload in hosted_demo.google_bodies
        if "requests" in payload
        for request_entry in payload["requests"]
    ]
    assert embed_entries
    assert all(entry["outputDimensionality"] == 384 for entry in embed_entries)
    task_types = {entry["taskType"] for entry in embed_entries}
    assert "RETRIEVAL_DOCUMENT" in task_types
    assert "RETRIEVAL_QUERY" in task_types
    assert any("models/gemini-embedding-001:batchEmbedContents" in str(request.url) for request in hosted_demo.google_requests)
    assert any(":countTokens" in str(request.url) for request in hosted_demo.google_requests)

    # Groq chat completions request carries the pinned model and the retrieved chunk text.
    assert hosted_demo.groq_requests
    groq = hosted_demo.groq_requests[0]
    assert str(groq.url).endswith("/chat/completions")
    assert groq.headers["authorization"] == "Bearer fake-groq-demo-key"
    payload = json.loads(groq.content.decode("utf-8"))
    assert payload["model"] == "openai/gpt-oss-120b"
    prompt_text = " ".join(message["content"] for message in payload["messages"])
    assert WATCH_FACT in prompt_text

    # Sanity: unrelated chunks are orthogonal to the query direction.
    unrelated = [
        list(embedding.embedding)
        for embedding in hosted_demo.session.embeddings
        if WATCH_FACT not in hosted_demo.session.chunks[embedding.chunk_id].content
    ]
    assert unrelated
    assert all(_cosine_similarity(_unit_vector(EXPECTED_DIRECTION), vector) == 0.0 for vector in unrelated)


def test_hosted_demo_e2e_groq_error_maps_to_contract_error(hosted_demo) -> None:
    upload = _upload_demo_policy(hosted_demo.client)
    assert upload.status_code == 202
    document_id = UUID(upload.json()["document_id"])
    assert _process_until_complete(hosted_demo, document_id) is True

    hosted_demo.groq_mode["status"] = 503
    questions = json.loads((DEMO_DIR / "questions.json").read_text(encoding="utf-8"))["questions"]
    q01 = next(question for question in questions if question["id"] == "demo_q01")
    query = hosted_demo.client.post(
        "/api/v1/query",
        json={"question": q01["question"], "top_k": 5, "stream": False},
    )
    assert query.status_code == 503
    body = query.json()
    assert body["code"] == "PROVIDER_UNAVAILABLE"
    # No fake answer and no abstention are returned for provider errors.
    assert "abstained" not in body and "citations" not in body
