from uuid import UUID
import pytest
from starlette.requests import Request
from starlette.testclient import TestClient

from app.api.dependencies import get_current_actor
from app.api.errors import APIProblem
from app.api.v1.endpoints.documents import _get_document_for_actor, _visible_document_predicate
from app.core.config import settings
from app.main import app
from app.models import Document, DocumentChunk, Embedding
from app.services.retrieval.service import RetrievalService


class MockEmbedder:
    model_name = "sentence-transformers/all-MiniLM-L6-v2"
    model_revision = "main"

    def embed_texts(self, texts, **kwargs):
        return [[0.1] * 384 for _ in texts]


class FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeDbSession:
    def __init__(self, rows=None):
        self.rows = rows or []

    async def execute(self, statement):
        return FakeResult(self.rows)

    async def get(self, model, ident):
        for r in self.rows:
            if isinstance(r, model) and r.id == ident:
                return r
        return None


def _make_doc(doc_id: UUID, roles: list[str]) -> Document:
    return Document(
        id=doc_id,
        org_id=UUID("00000000-0000-4000-8000-000000000032"),
        uploaded_by=UUID("00000000-0000-4000-8000-000000000031"),
        title="Test Document",
        source_type="docx",
        original_filename="test.docx",
        storage_key="test.docx",
        file_size_bytes=100,
        allowed_roles=roles,
        status="complete",
        chunk_count=1,
        is_deleted=False,
    )


def test_demo_actor_role_default_stays_orgadmin():
    """Default DEMO_ACTOR_ROLE is orgadmin and yields full orgadmin effective roles."""
    assert settings.DEMO_ACTOR_ROLE == "orgadmin"
    req = Request({"type": "http", "query_string": b"", "headers": []})
    actor = get_current_actor(req)
    assert actor.effective_roles == ["orgadmin", "manager", "employee"]


@pytest.mark.asyncio
async def test_employee_effective_roles_and_manager_document_isolation(monkeypatch):
    """With DEMO_ACTOR_ROLE=employee, effective roles are only employee, isolating manager docs."""
    monkeypatch.setattr(settings, "DEMO_ACTOR_ROLE", "employee")
    req = Request({"type": "http", "query_string": b"", "headers": []})
    actor = get_current_actor(req)
    assert actor.effective_roles == ["employee"]

    doc_emp_id = UUID("11111111-1111-4000-8000-000000000001")
    doc_mgr_id = UUID("22222222-2222-4000-8000-000000000002")
    doc_emp = _make_doc(doc_emp_id, ["employee"])
    doc_mgr = _make_doc(doc_mgr_id, ["manager"])

    session = FakeDbSession(rows=[doc_emp, doc_mgr])

    # 1. Direct document retrieval via _get_document_for_actor
    allowed = await _get_document_for_actor(session, actor, doc_emp_id)
    assert allowed.id == doc_emp_id

    with pytest.raises(APIProblem) as exc_info:
        await _get_document_for_actor(session, actor, doc_mgr_id)
    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "FORBIDDEN"

    # 2. RetrievalService post-filters manager-only document rows
    chunk_mgr = DocumentChunk(
        id=UUID("33333333-3333-4000-8000-000000000003"),
        org_id=actor.org_id,
        document_id=doc_mgr_id,
        chunk_index=0,
        content="Manager salary review details",
        token_count=10,
    )
    embedding_mgr = Embedding(
        id=UUID("44444444-4444-4000-8000-000000000004"),
        org_id=actor.org_id,
        document_id=doc_mgr_id,
        chunk_id=chunk_mgr.id,
        model_name="sentence-transformers/all-MiniLM-L6-v2",
        model_revision="main",
        embedding=[0.1] * 384,
        is_active=True,
    )
    retrieval_session = FakeDbSession(rows=[(embedding_mgr, chunk_mgr, doc_mgr, 0.95)])
    service = RetrievalService(MockEmbedder(), minimum_similarity=0.35)
    evidence = await service.retrieve(retrieval_session, actor, "salary review", 5)
    assert evidence == []

    # 3. Document list predicate includes role filtering
    predicates = _visible_document_predicate(actor)
    assert len(predicates) == 3


@pytest.mark.parametrize(
    "query_or_header",
    [
        {"query_string": b"role=manager", "headers": []},
        {"query_string": b"effective_roles=manager", "headers": []},
        {"query_string": b"x-role=manager", "headers": []},
        {"query_string": b"", "headers": [(b"x-role", b"superadmin")]},
        {"query_string": b"", "headers": [(b"role", b"superadmin")]},
        {"query_string": b"", "headers": [(b"x-org-id", b"00000000-0000-4000-8000-000000000032")]},
    ],
)
def test_client_role_and_identity_inputs_are_rejected(query_or_header):
    """Caller-supplied identity in query params or headers must return 422."""
    req = Request({"type": "http", **query_or_header})
    with pytest.raises(APIProblem) as exc_info:
        get_current_actor(req)
    assert exc_info.value.status_code == 422
    assert exc_info.value.code == "VALIDATION_ERROR"


def test_client_query_endpoint_rejects_client_role():
    """Client POST /api/v1/query with extra role field is rejected with 422."""
    client = TestClient(app)
    resp = client.post(
        "/api/v1/query",
        json={"question": "What is the policy?", "role": "superadmin"},
    )
    assert resp.status_code == 422
    assert resp.json()["code"] == "VALIDATION_ERROR"