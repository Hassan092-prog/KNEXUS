"""Focused mocked regressions for Google hosted embedding adapter and task wiring."""
from math import isclose, sqrt
from uuid import uuid4
import json
import httpx
import pytest

from app.core.dispatch_policy import BlockedLiveDispatchPolicy, LiveInferenceBlockedError, MockDispatchPolicy
from app.models import Document, DocumentChunk, Embedding, IngestionJob
from app.schemas import ActorContext
from app.services.ingestion.embedding import (
    GoogleGenAIEmbedder,
    get_default_embedder,
    validate_embeddings,
)
from app.services.ingestion.errors import EmbeddingUnavailableError
from app.services.ingestion.parsing import ParsedSection
from app.services.ingestion.processor import process_document
from app.services.retrieval.service import RetrievalService


def test_google_embedder_blocked_by_default_before_http():
    # Even with credentials, unapproved live dispatch must fail before creating client or sending HTTP
    embedder = GoogleGenAIEmbedder(
        api_key="real-looking-key-12345",
        dispatch_policy=BlockedLiveDispatchPolicy(),
    )
    with pytest.raises(LiveInferenceBlockedError, match="blocked"):
        embedder.embed_texts(["Unapproved live attempt"])


def test_google_embedder_missing_key_fails_closed():
    embedder = GoogleGenAIEmbedder(
        api_key=None,
        dispatch_policy=MockDispatchPolicy(),
    )
    with pytest.raises(EmbeddingUnavailableError, match="Set EMBEDDING_API_KEY"):
        embedder.embed_texts(["test document text"])


def test_google_embedder_empty_input_returns_empty():
    embedder = GoogleGenAIEmbedder(
        api_key="test-key",
        dispatch_policy=MockDispatchPolicy(),
    )
    assert embedder.embed_texts([]) == []


def test_google_embedder_max_input_tokens():
    embedder = GoogleGenAIEmbedder(api_key="test-key")
    assert embedder.get_max_input_tokens() == 2048


def test_google_embedder_unsupported_task_type_fails():
    embedder = GoogleGenAIEmbedder(
        api_key="test-key",
        dispatch_policy=MockDispatchPolicy(),
    )
    with pytest.raises(EmbeddingUnavailableError, match="Unsupported Google embedding task_type"):
        embedder.embed_texts(["sample"], task_type="INVALID_TASK")


def test_google_embedder_successful_batch_embedding():
    recorded_requests = []

    def mock_handler(request: httpx.Request) -> httpx.Response:
        recorded_requests.append(request)
        data = json.loads(request.content.decode("utf-8"))
        reqs = data.get("requests", [])
        embeddings = []
        for i, _ in enumerate(reqs):
            raw_vals = [float(i + 1) for _ in range(384)]
            embeddings.append({"values": raw_vals})
        return httpx.Response(200, json={"embeddings": embeddings})

    transport = httpx.MockTransport(mock_handler)
    embedder = GoogleGenAIEmbedder(
        api_key="mock-gemini-key",
        output_dimensions=384,
        task_type="RETRIEVAL_DOCUMENT",
        transport=transport,
        dispatch_policy=MockDispatchPolicy(),
    )

    texts = ["First chunk of text", "Second chunk of text"]
    vectors = embedder.embed_texts(texts)

    assert len(vectors) == 2
    assert len(recorded_requests) == 1
    req = recorded_requests[0]
    assert req.headers["x-goog-api-key"] == "mock-gemini-key"
    assert "models/gemini-embedding-001:batchEmbedContents" in str(req.url)

    req_body = json.loads(req.content.decode("utf-8"))
    assert len(req_body["requests"]) == 2
    assert req_body["requests"][0]["taskType"] == "RETRIEVAL_DOCUMENT"
    assert req_body["requests"][0]["outputDimensionality"] == 384
    assert req_body["requests"][0]["content"]["parts"][0]["text"] == "First chunk of text"

    for v in vectors:
        assert len(v) == 384
        norm = sqrt(sum(x * x for x in v))
        assert isclose(norm, 1.0, rel_tol=1e-5)


def test_google_embedder_rejects_boolean_and_non_numeric_elements():
    def mock_handler_bool(request: httpx.Request) -> httpx.Response:
        vals = [1.0] * 383 + [True]  # Boolean element
        return httpx.Response(200, json={"embeddings": [{"values": vals}]})

    transport = httpx.MockTransport(mock_handler_bool)
    embedder = GoogleGenAIEmbedder(
        api_key="mock-key",
        transport=transport,
        dispatch_policy=MockDispatchPolicy(),
    )
    with pytest.raises(EmbeddingUnavailableError, match="must be a finite number"):
        embedder.embed_texts(["Text with bool element"])


def test_google_embedder_rejects_zero_norm_vector():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [{"values": [0.0] * 384}]})

    transport = httpx.MockTransport(mock_handler)
    embedder = GoogleGenAIEmbedder(
        api_key="mock-key",
        transport=transport,
        dispatch_policy=MockDispatchPolicy(),
    )
    with pytest.raises(EmbeddingUnavailableError, match="zero or non-finite norm"):
        embedder.embed_texts(["Text with zero vector"])


def test_google_embedder_rejects_service_error_payload():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"error": {"code": 400, "message": "API key not valid. Please pass a valid API key."}},
        )

    transport = httpx.MockTransport(mock_handler)
    embedder = GoogleGenAIEmbedder(
        api_key="mock-key",
        transport=transport,
        dispatch_policy=MockDispatchPolicy(),
    )
    with pytest.raises(EmbeddingUnavailableError, match="Google embedding service error"):
        embedder.embed_texts(["Text with error payload"])


def test_google_embedder_dimension_mismatch_fails():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [{"values": [1.0] * 768}]})

    transport = httpx.MockTransport(mock_handler)
    embedder = GoogleGenAIEmbedder(
        api_key="mock-key",
        output_dimensions=384,
        transport=transport,
        dispatch_policy=MockDispatchPolicy(),
    )
    with pytest.raises(EmbeddingUnavailableError, match="dimension mismatch"):
        embedder.embed_texts(["Text expecting 384"])


def test_google_embedder_maps_http_errors():
    for status, match_str in [
        (401, "authentication failed"),
        (403, "authentication failed"),
        (429, "rate limit exceeded"),
        (503, "HTTP 503"),
    ]:
        def mock_handler(request: httpx.Request, code=status) -> httpx.Response:
            return httpx.Response(code, text="Error payload")

        transport = httpx.MockTransport(mock_handler)
        embedder = GoogleGenAIEmbedder(
            api_key="mock-key",
            transport=transport,
            dispatch_policy=MockDispatchPolicy(),
        )
        with pytest.raises(EmbeddingUnavailableError, match=match_str):
            embedder.embed_texts(["Test error mapping"])


def test_google_embedder_maps_timeout():
    def mock_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Read timed out")

    transport = httpx.MockTransport(mock_handler)
    embedder = GoogleGenAIEmbedder(
        api_key="mock-key",
        transport=transport,
        dispatch_policy=MockDispatchPolicy(),
    )
    with pytest.raises(EmbeddingUnavailableError, match="timed out"):
        embedder.embed_texts(["Test timeout"])


@pytest.mark.asyncio
async def test_retrieval_service_path_sends_retrieval_query():
    # Prove the actual retrieval service sends taskType='RETRIEVAL_QUERY'
    recorded_tasks = []

    class MockTaskRecordingEmbedder:
        model_name = "gemini-embedding-001"
        model_revision = "001"

        def embed_texts(self, texts, *, task_type=None, **kwargs):
            recorded_tasks.append(task_type)
            return [[0.1] * 384]

    embedder = MockTaskRecordingEmbedder()
    service = RetrievalService(embedder=embedder)

    class MockResult:
        def all(self):
            return []

    class MockSession:
        async def execute(self, stmt):
            return MockResult()

    actor = ActorContext(
        org_id=uuid4(),
        user_id=uuid4(),
        effective_roles=["employee"],
    )

    await service.retrieve(MockSession(), actor, "What is the policy?", top_k=5)
    assert len(recorded_tasks) == 1
    assert recorded_tasks[0] == "RETRIEVAL_QUERY"


@pytest.mark.asyncio
async def test_ingestion_processor_path_sends_retrieval_document():
    # Prove the actual ingestion document processing sends taskType='RETRIEVAL_DOCUMENT'
    recorded_tasks = []

    class MockTaskRecordingEmbedder:
        model_name = "gemini-embedding-001"
        model_revision = "001"

        def embed_texts(self, texts, *, task_type=None, **kwargs):
            recorded_tasks.append(task_type)
            return [[0.1] * 384]

    class FakeTokenizer:
        model_max_length = 256
        def encode(self, text, add_special_tokens=False):
            return [1] * len(text)
        def num_special_tokens_to_add(self, pair=False):
            return 0

    embedder = MockTaskRecordingEmbedder()
    org_id = uuid4()
    doc_id = uuid4()
    document = Document(
        id=doc_id,
        org_id=org_id,
        title="Doc",
        source_type="docx",
        storage_key="test-key",
        status="queued",
        allowed_roles=["employee"],
        chunk_count=0,
    )
    job = IngestionJob(
        id=uuid4(),
        org_id=org_id,
        document_id=doc_id,
        attempt_number=1,
        status="queued",
    )

    class MockProcessorSession:
        def __init__(self):
            self.added = []
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            pass
        async def get(self, entity, ident):
            if entity is Document:
                return document
            return None
        async def execute(self, stmt):
            class ScalarOne:
                def scalar_one_or_none(self):
                    return job
            return ScalarOne()
        def add(self, item):
            self.added.append(item)
        async def flush(self):
            pass
        async def commit(self):
            pass

    session = MockProcessorSession()
    sections = [ParsedSection("Paragraph text content", 1, {"page": 1})]

    success = await process_document(
        doc_id,
        parsed_sections=sections,
        session_factory=lambda: session,
        embedder=embedder,
        tokenizer=FakeTokenizer(),
    )
    assert success is True
    assert len(recorded_tasks) >= 1
    assert all(t == "RETRIEVAL_DOCUMENT" for t in recorded_tasks)


@pytest.mark.asyncio
async def test_embedder_internal_type_error_not_caught_or_retried():
    # Prove that an embedder raising an internal TypeError is invoked exactly once
    # and the exception propagates directly without exception-driven retry or task-type mutation.
    call_records = []

    class TypeErrorFailingEmbedder:
        model_name = "gemini-embedding-001"
        model_revision = "001"

        def embed_texts(self, texts, *, task_type=None, **kwargs):
            call_records.append({"texts": texts, "task_type": task_type})
            raise TypeError("Simulated internal TypeError inside embedder")

    embedder = TypeErrorFailingEmbedder()
    service = RetrievalService(embedder=embedder)

    class MockSession:
        async def execute(self, stmt):
            pass

    actor = ActorContext(
        org_id=uuid4(),
        user_id=uuid4(),
        effective_roles=["employee"],
    )

    with pytest.raises(TypeError, match="Simulated internal TypeError inside embedder"):
        await service.retrieve(MockSession(), actor, "Question?", top_k=3)

    assert len(call_records) == 1
    assert call_records[0]["task_type"] == "RETRIEVAL_QUERY"


@pytest.mark.asyncio
async def test_ingestion_internal_type_error_not_caught_or_retried():
    # Prove that ingestion embedder raising TypeError is called exactly once without retry
    call_records = []

    class TypeErrorFailingEmbedder:
        model_name = "gemini-embedding-001"
        model_revision = "001"

        def embed_texts(self, texts, *, task_type=None, **kwargs):
            call_records.append({"texts": texts, "task_type": task_type})
            raise TypeError("Simulated internal TypeError in ingestion embedder")

    class FakeTokenizer:
        model_max_length = 256
        def encode(self, text, add_special_tokens=False):
            return [1] * len(text)
        def num_special_tokens_to_add(self, pair=False):
            return 0

    embedder = TypeErrorFailingEmbedder()
    org_id = uuid4()
    doc_id = uuid4()
    document = Document(
        id=doc_id, org_id=org_id, title="Doc", source_type="docx",
        storage_key="k", status="queued", allowed_roles=["employee"], chunk_count=0
    )
    job = IngestionJob(id=uuid4(), org_id=org_id, document_id=doc_id, attempt_number=1, status="queued")

    class MockSession:
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def get(self, *args):
            return document
        async def execute(self, *args):
            class S:
                def scalar_one_or_none(self):
                    return job
            return S()
        def add(self, item):
            pass
        async def flush(self):
            pass
        async def commit(self):
            pass

    sections = [ParsedSection("Sample text", 1, {"page": 1})]
    res = await process_document(
        doc_id,
        parsed_sections=sections,
        session_factory=lambda: MockSession(),
        embedder=embedder,
        tokenizer=FakeTokenizer(),
    )
    assert res is False
    assert len(call_records) == 1
    assert call_records[0]["task_type"] == "RETRIEVAL_DOCUMENT"
