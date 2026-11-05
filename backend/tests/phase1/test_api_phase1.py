"""Offline contract tests for the document and query HTTP routes."""
from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest
from docx import Document as WordDocument
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_actor, get_generation_service, get_retrieval_service
from app.core.database import get_db
from app.main import app
from app.models import Document, IngestionJob
from app.schemas import EvidenceChunk, GenerationResult
from app.services.generation.errors import (
    MalformedOutputError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


DOC_ID = UUID("00000000-0000-4000-8000-000000000501")
CHUNK_ID = UUID("00000000-0000-4000-8000-000000000502")
ORG_ID = UUID("00000000-0000-4000-8000-000000000032")
USER_ID = UUID("00000000-0000-4000-8000-000000000031")
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


def make_docx() -> bytes:
    doc = WordDocument()
    doc.add_paragraph("Annual leave is twenty days.")
    stream = BytesIO()
    doc.save(stream)
    return stream.getvalue()


class Result:
    def __init__(self, rows=(), scalar=None):
        self._rows = list(rows)
        self._scalar = scalar

    def scalars(self):
        return self

    def all(self):
        return self._rows

    def scalar_one_or_none(self):
        return self._rows[0] if self._rows else None

    def scalar(self):
        return self._scalar


class FakeSession:
    def __init__(self):
        self.added = []
        self.documents = {}
        self.jobs = {}
        self.statements = []
        self.commits = 0
        self.rollbacks = 0

    def add(self, row):
        self.added.append(row)
        if isinstance(row, Document):
            self.documents[row.id] = row
        elif isinstance(row, IngestionJob):
            self.jobs[row.id] = row

    async def flush(self):
        return None

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1

    async def get(self, model, key):
        if model is Document:
            return self.documents.get(key)
        return None

    async def scalar(self, statement):
        self.statements.append(statement)
        return len(self.documents)

    async def execute(self, statement):
        self.statements.append(statement)
        if "ingestion_jobs" in str(statement):
            return Result(sorted(self.jobs.values(), key=lambda j: j.attempt_number, reverse=True)[:1])
        if "documents" in str(statement):
            return Result(self.documents.values())
        return Result()


class FakeRetrieval:
    def __init__(self, evidence):
        self.evidence = evidence
        self.calls = []

    async def retrieve(self, session, actor, question, top_k):
        self.calls.append((actor, question, top_k))
        return self.evidence


class FakeGenerator:
    provider = "fake"
    model = "fake"

    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error
        self.requests = []

    async def generate(self, request):
        self.requests.append(request)
        if self.error:
            raise self.error
        return self.result


@pytest.fixture
def api_client(monkeypatch, tmp_path):
    session = FakeSession()

    async def override_db():
        yield session

    async def no_background_work(*args, **kwargs):
        return True

    from app.api.v1.endpoints import documents as document_routes
    monkeypatch.setattr(document_routes, "process_document", no_background_work)
    monkeypatch.setattr(
        __import__("app.core.config", fromlist=["settings"]).settings,
        "DOCUMENT_STORAGE_ROOT",
        tmp_path / "private",
    )
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, session
    app.dependency_overrides.clear()


def test_upload_accepts_one_valid_docx_repeated_roles_and_commits_before_202(
    api_client,
):
    client, session = api_client
    response = client.post(
        "/api/v1/documents/upload",
        files=[
            ("file", ("handbook.docx", make_docx(), DOCX_MIME)),
            ("allowed_roles", (None, "employee")),
            ("allowed_roles", (None, "manager")),
            ("title", (None, "Team Handbook")),
            ("description", (None, "Synthetic test")),
        ],
    )
    assert response.status_code == 202
    body = response.json()
    assert set(body) == {"document_id", "task_id", "status", "message"}
    assert body["status"] == "queued"
    assert session.commits == 1
    document = next(row for row in session.added if isinstance(row, Document))
    job = next(row for row in session.added if isinstance(row, IngestionJob))
    assert document.allowed_roles == ["employee", "manager"]
    assert document.org_id == ORG_ID and document.uploaded_by == USER_ID
    assert document.original_filename == "handbook.docx"
    assert document.storage_key.endswith(".docx")
    assert document.status == job.status == "queued"
    assert body["document_id"] == str(document.id)
    assert body["task_id"] == str(job.id)
    assert Path(document_routes_storage_path(document.storage_key)).is_file()


def document_routes_storage_path(storage_key):
    from app.services.ingestion.storage import resolve_storage_path
    return resolve_storage_path(storage_key)


@pytest.mark.parametrize(
    ("extra_form", "status", "code"),
    [
        (("role", "superadmin"), 422, "VALIDATION_ERROR"),
        (("org_id", str(ORG_ID)), 422, "VALIDATION_ERROR"),
        (("effective_roles", "superadmin"), 422, "VALIDATION_ERROR"),
    ],
)
def test_upload_rejects_caller_identity_without_persisting(
    api_client, extra_form, status, code
):
    client, session = api_client
    response = client.post(
        "/api/v1/documents/upload",
        files=[
            ("file", ("handbook.docx", make_docx(), DOCX_MIME)),
            ("allowed_roles", (None, "employee")),
            (extra_form[0], (None, extra_form[1])),
        ],
    )
    assert response.status_code == status
    assert response.json()["code"] == code
    assert response.json()["request_id"] == response.headers["x-request-id"]
    assert session.added == []


def test_upload_rejects_bad_file_signature_with_safe_error(api_client):
    client, session = api_client
    response = client.post(
        "/api/v1/documents/upload",
        files=[
            ("file", ("fake.pdf", b"not a PDF", "application/pdf")),
            ("allowed_roles", (None, "employee")),
        ],
    )
    assert response.status_code == 400
    assert response.json()["code"] == "INVALID_FILE"
    assert session.added == []


def _document(*, org_id=ORG_ID, allowed_roles=None, status="complete", deleted=False):
    return Document(
        id=DOC_ID,
        org_id=org_id,
        uploaded_by=USER_ID,
        title="Team Handbook",
        source_type="docx",
        original_filename="handbook.docx",
        storage_key="a" * 32 + ".docx",
        file_size_bytes=1024,
        allowed_roles=allowed_roles or ["employee"],
        status=status,
        chunk_count=1,
        description=None,
        metadata_json={},
        is_deleted=deleted,
        created_at=datetime.now(timezone.utc),
    )


def test_document_detail_and_status_return_contract_models(api_client):
    client, session = api_client
    document = _document()
    session.documents[DOC_ID] = document
    job = IngestionJob(
        id=UUID("00000000-0000-4000-8000-000000000503"),
        org_id=ORG_ID,
        document_id=DOC_ID,
        attempt_number=1,
        status="complete",
        chunks_processed=1,
        total_chunks=1,
        failure_code=None,
        failure_message=None,
    )
    session.jobs[job.id] = job

    detail = client.get(f"/api/v1/documents/{DOC_ID}")
    assert detail.status_code == 200
    assert detail.json()["id"] == str(DOC_ID)
    assert detail.json()["metadata"] == {}

    status = client.get(f"/api/v1/documents/{DOC_ID}/status")
    assert status.status_code == 200
    assert status.json() == {
        "document_id": str(DOC_ID),
        "status": "complete",
        "chunks_processed": 1,
        "total_chunks": 1,
        "progress_percent": 100,
        "failure_code": None,
        "failure_message": None,
    }


def test_document_access_distinguishes_same_tenant_role_denial_from_cross_tenant(api_client):
    client, session = api_client
    session.documents[DOC_ID] = _document(allowed_roles=["superadmin"])
    denied = client.get(f"/api/v1/documents/{DOC_ID}")
    assert denied.status_code == 403
    assert denied.json()["code"] == "FORBIDDEN"

    session.documents[DOC_ID] = _document(org_id=UUID("00000000-0000-4000-8000-000000000777"))
    hidden = client.get(f"/api/v1/documents/{DOC_ID}")
    assert hidden.status_code == 404
    assert hidden.json()["code"] == "NOT_FOUND"


def test_document_list_compiles_tenant_and_role_filters_before_page(api_client):
    client, session = api_client
    response = client.get("/api/v1/documents?limit=2&offset=1")
    assert response.status_code == 200
    assert response.json()["meta"] == {"total": 0, "limit": 2, "offset": 1}
    sql = str(session.statements[0].compile())
    assert "org_id" in sql and "allowed_roles" in sql and "is_deleted" in sql
    assert session.statements[1]._limit_clause.value == 2
    assert session.statements[1]._offset_clause.value == 1


def _evidence():
    return EvidenceChunk(
        citation_id=1,
        chunk_id=CHUNK_ID,
        document_id=DOC_ID,
        document_title="Team Handbook",
        chunk_index=0,
        page=None,
        content="Annual leave is twenty days.",
        similarity_score=0.91,
    )


def test_query_returns_backend_assembled_citations_and_correlation_id(api_client):
    client, _session = api_client
    retrieval = FakeRetrieval([_evidence()])
    generation = FakeGenerator(
        GenerationResult(
            answer="Annual leave is twenty days [1].",
            cited_ids=[1],
            abstained=False,
            abstention_reason=None,
        )
    )
    app.dependency_overrides[get_retrieval_service] = lambda: retrieval
    app.dependency_overrides[get_generation_service] = lambda: generation
    response = client.post(
        "/api/v1/query",
        json={"question": "How many leave days?", "top_k": 5, "stream": False},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "Annual leave is twenty days [1]."
    assert body["citations"][0]["chunk_id"] == str(CHUNK_ID)
    assert body["citations"][0]["document_title"] == "Team Handbook"
    assert body["citations"][0]["excerpt"] == "Annual leave is twenty days."
    assert body["abstained"] is False
    assert body["session_id"]
    assert body["meta"]["model"] == "fake"
    assert retrieval.calls[0][0].org_id == ORG_ID
    assert generation.requests[0].evidence == [_evidence()]


def test_query_abstains_before_inference_when_retrieval_returns_no_safe_evidence(api_client):
    client, _session = api_client
    retrieval = FakeRetrieval([])
    generation = FakeGenerator()
    app.dependency_overrides[get_retrieval_service] = lambda: retrieval
    app.dependency_overrides[get_generation_service] = lambda: generation
    response = client.post("/api/v1/query", json={"question": "Unsupported?"})
    assert response.status_code == 200
    assert response.json()["abstained"] is True
    assert response.json()["answer"] is None
    assert response.json()["citations"] == []
    assert generation.requests == []


@pytest.mark.parametrize(
    ("error", "status", "code"),
    [
        (ProviderTimeoutError("private details"), 504, "PROVIDER_UNAVAILABLE"),
        (ProviderUnavailableError("private details"), 503, "PROVIDER_UNAVAILABLE"),
        (MalformedOutputError("private details"), 502, "INVALID_CITATIONS"),
    ],
)
def test_query_maps_provider_failures_to_safe_error_envelopes(
    api_client, error, status, code
):
    client, _session = api_client
    app.dependency_overrides[get_retrieval_service] = lambda: FakeRetrieval([_evidence()])
    app.dependency_overrides[get_generation_service] = lambda: FakeGenerator(error=error)
    response = client.post("/api/v1/query", json={"question": "How many days?"})
    assert response.status_code == status
    assert response.json()["code"] == code
    assert response.json()["request_id"] == response.headers["x-request-id"]
    assert "private details" not in response.text


def test_query_rejects_identity_and_unsupported_stream_without_calling_services(api_client):
    client, _session = api_client
    response = client.post(
        "/api/v1/query",
        json={"question": "How many days?", "user_id": str(USER_ID)},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"

    response = client.post(
        "/api/v1/query",
        json={"question": "How many days?", "stream": True},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"

    response = client.post(
        "/api/v1/query",
        headers={"X_User_ID": str(USER_ID)},
        json={"question": "How many days?"},
    )
    assert response.status_code == 422
    assert response.json()["code"] == "VALIDATION_ERROR"


def test_openapi_exposes_phase_one_routes_and_cors_preflight(api_client):
    client, _session = api_client
    schema = client.get("/api/v1/openapi.json").json()
    paths = schema["paths"]
    assert "/api/v1/documents/upload" in paths
    assert paths["/api/v1/documents/upload"]["post"]["responses"]["202"]
    assert "/api/v1/documents/{document_id}/status" in paths
    assert "/api/v1/query" in paths

    preflight = client.options(
        "/api/v1/query",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"
