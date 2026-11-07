from pathlib import Path
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


def test_google_embedder_missing_key_fails_closed(tmp_path: Path):
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=tmp_path / "ledger.json"))
    embedder = GoogleGenAIEmbedder(
        api_key=None,
        dispatch_policy=MockDispatchPolicy(),
        quota_ledger=ledger,
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


def test_google_embedder_unsupported_task_type_fails(tmp_path: Path):
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=tmp_path / "ledger.json"))
    embedder = GoogleGenAIEmbedder(
        api_key="test-key",
        dispatch_policy=MockDispatchPolicy(),
        quota_ledger=ledger,
    )
    with pytest.raises(EmbeddingUnavailableError, match="Unsupported Google embedding task_type"):
        embedder.embed_texts(["sample"], task_type="INVALID_TASK")


def test_google_embedder_successful_batch_embedding(tmp_path: Path):
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=tmp_path / "ledger.json"))
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
        quota_ledger=ledger,
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


def test_google_embedder_rejects_boolean_and_non_numeric_elements(tmp_path: Path):
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=tmp_path / "ledger.json"))
    def mock_handler_bool(request: httpx.Request) -> httpx.Response:
        vals = [1.0] * 383 + [True]  # Boolean element
        return httpx.Response(200, json={"embeddings": [{"values": vals}]})

    transport = httpx.MockTransport(mock_handler_bool)
    embedder = GoogleGenAIEmbedder(
        api_key="mock-key",
        transport=transport,
        dispatch_policy=MockDispatchPolicy(),
        quota_ledger=ledger,
    )
    with pytest.raises(EmbeddingUnavailableError, match="must be a finite number"):
        embedder.embed_texts(["Text with bool element"])


def test_google_embedder_rejects_zero_norm_vector(tmp_path: Path):
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=tmp_path / "ledger.json"))
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [{"values": [0.0] * 384}]})

    transport = httpx.MockTransport(mock_handler)
    embedder = GoogleGenAIEmbedder(
        api_key="mock-key",
        transport=transport,
        dispatch_policy=MockDispatchPolicy(),
        quota_ledger=ledger,
    )
    with pytest.raises(EmbeddingUnavailableError, match="zero or non-finite norm"):
        embedder.embed_texts(["Text with zero vector"])


def test_google_embedder_rejects_service_error_payload(tmp_path: Path):
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=tmp_path / "ledger.json"))
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
        quota_ledger=ledger,
    )
    with pytest.raises(EmbeddingUnavailableError, match="Google embedding service error"):
        embedder.embed_texts(["Text with error payload"])


def test_google_embedder_dimension_mismatch_fails(tmp_path: Path):
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=tmp_path / "ledger.json"))
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"embeddings": [{"values": [1.0] * 768}]})

    transport = httpx.MockTransport(mock_handler)
    embedder = GoogleGenAIEmbedder(
        api_key="mock-key",
        output_dimensions=384,
        transport=transport,
        dispatch_policy=MockDispatchPolicy(),
        quota_ledger=ledger,
    )
    with pytest.raises(EmbeddingUnavailableError, match="dimension mismatch"):
        embedder.embed_texts(["Text expecting 384"])


def test_google_embedder_maps_http_errors(tmp_path: Path):
    for status, match_str in [
        (401, "authentication failed"),
        (403, "authentication failed"),
        (429, "rate limit exceeded"),
        (503, "HTTP 503"),
    ]:
        ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=tmp_path / f"ledger_{status}.json"))
        def mock_handler(request: httpx.Request, code=status) -> httpx.Response:
            return httpx.Response(code, text="Error payload")

        transport = httpx.MockTransport(mock_handler)
        embedder = GoogleGenAIEmbedder(
            api_key="mock-key",
            transport=transport,
            dispatch_policy=MockDispatchPolicy(),
            quota_ledger=ledger,
        )
        with pytest.raises(EmbeddingUnavailableError, match=match_str):
            embedder.embed_texts(["Test error mapping"])


def test_google_embedder_maps_timeout(tmp_path: Path):
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=tmp_path / "ledger.json"))
    def mock_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Read timed out")

    transport = httpx.MockTransport(mock_handler)
    embedder = GoogleGenAIEmbedder(
        api_key="mock-key",
        transport=transport,
        dispatch_policy=MockDispatchPolicy(),
        quota_ledger=ledger,
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
# ==============================================================================
# Task 2: Quota metering regressions for GoogleGenAIEmbedder
# ==============================================================================

from app.core.quota import QuotaConfig, QuotaLedger, RateLimitExceededError
from app.services.ingestion.errors import EmbeddingSettlementError


def test_google_embedder_reserves_and_settles_on_200_with_usage(tmp_path):
    """Reserve before dispatch, settle on 200 with usage metadata."""
    state_file = tmp_path / "ledger_embed_200.json"
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=state_file))

    embed_response = {
        "embeddings": [{"values": [0.1, 0.2, 0.3]}],
        "usageMetadata": {
            "promptTokenCount": 12,
            "totalTokenCount": 12,
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=embed_response)

    transport = httpx.MockTransport(handler)
    embedder = GoogleGenAIEmbedder(
        api_key="mock-key-123",
        output_dimensions=3,
        transport=transport,
        dispatch_policy=MockDispatchPolicy("google"),
        quota_ledger=ledger,
    )

    vecs = embedder.embed_texts(["sample text"])
    assert len(vecs) == 1

    with open(state_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data.get("active_reservations", {})) == 0
    settled = data.get("settled_requests", [])
    assert len(settled) == 1
    rec = settled[0]
    assert rec["success"] is True
    assert rec["usage_valid"] is True
    assert rec["tokens_unresolved"] is False
    assert rec["usage"] == {"prompt_tokens": 12, "completion_tokens": 0, "total_tokens": 12}


def test_google_embedder_missing_usage_leaves_tokens_unresolved(tmp_path):
    """Missing usageMetadata settles with tokens_unresolved=True."""
    state_file = tmp_path / "ledger_embed_nousage.json"
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=state_file))

    embed_response = {
        "embeddings": [{"values": [0.1, 0.2, 0.3]}],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=embed_response)

    transport = httpx.MockTransport(handler)
    embedder = GoogleGenAIEmbedder(
        api_key="mock-key-123",
        output_dimensions=3,
        transport=transport,
        dispatch_policy=MockDispatchPolicy("google"),
        quota_ledger=ledger,
    )

    vecs = embedder.embed_texts(["sample text"])
    assert len(vecs) == 1

    with open(state_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    settled = data.get("settled_requests", [])
    assert len(settled) == 1
    rec = settled[0]
    assert rec["success"] is True
    assert rec["usage"] is None
    assert rec["tokens_unresolved"] is True


def test_google_embedder_429_trips_tripwire_no_retries(tmp_path):
    """HTTP 429 records settlement failure, trips circuit breaker, raises without retries."""
    state_file = tmp_path / "ledger_embed_429.json"
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=state_file))

    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(429, json={"error": "Rate limit exceeded"})

    transport = httpx.MockTransport(handler)
    embedder = GoogleGenAIEmbedder(
        api_key="mock-key-123",
        output_dimensions=3,
        transport=transport,
        dispatch_policy=MockDispatchPolicy("google"),
        quota_ledger=ledger,
    )

    # First call fails with EmbeddingUnavailableError
    with pytest.raises(EmbeddingUnavailableError, match="rate limit exceeded"):
        embedder.embed_texts(["sample text"])

    assert call_count == 1

    # Verify ledger state has rate limit set
    with open(state_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    scope_info = data.get("scopes", {}).get("google:gemini-embedding-001", {})
    assert scope_info.get("rate_limited") is True

    # Second call trips circuit breaker during reserve_attempt BEFORE any HTTP call
    with pytest.raises(RateLimitExceededError, match="rate limit active"):
        embedder.embed_texts(["another text"])

    # No additional HTTP call was made
    assert call_count == 1


def test_google_embedder_settlement_failure_preserves_reservation_and_raises(tmp_path):
    """Settlement failure raises EmbeddingSettlementError and preserves reservation."""
    state_file = tmp_path / "ledger_embed_settle_fail.json"
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=state_file))

    def failing_settle(attempt_id, **kwargs):
        raise OSError("Disk full during settlement")

    ledger.settle_attempt = failing_settle

    embed_response = {
        "embeddings": [{"values": [0.1, 0.2, 0.3]}],
        "usageMetadata": {"promptTokenCount": 10, "totalTokenCount": 10},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=embed_response)

    transport = httpx.MockTransport(handler)
    embedder = GoogleGenAIEmbedder(
        api_key="mock-key-123",
        output_dimensions=3,
        transport=transport,
        dispatch_policy=MockDispatchPolicy("google"),
        quota_ledger=ledger,
    )

    with pytest.raises(EmbeddingSettlementError, match="Quota settlement failed"):
        embedder.embed_texts(["sample text"])

    # Active reservation remains un-settled (outstanding preserved)
    with open(state_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data.get("active_reservations", {})) == 1


def test_google_embedder_without_ledger_fails_closed_when_dispatch_authorized():
    """F3: When dispatch is authorized, GoogleGenAIEmbedder without a ledger fails closed before HTTP."""
    embedder = GoogleGenAIEmbedder(
        api_key="test-key",
        dispatch_policy=MockDispatchPolicy("google"),
        quota_ledger=None,
    )
    with pytest.raises(EmbeddingUnavailableError, match="A configured QuotaLedger is strictly required"):
        embedder.embed_texts(["any test text"])


def test_google_embedder_settles_on_base_exception(tmp_path: Path):
    """F5: Exactly-once settlement is guaranteed on BaseException (e.g. GeneratorExit)."""
    state_file = tmp_path / "ledger_base_exc.json"
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=state_file))

    def raise_generator_exit(req):
        raise GeneratorExit("simulated generator exit / cancellation")

    transport = httpx.MockTransport(raise_generator_exit)
    embedder = GoogleGenAIEmbedder(
        api_key="mock-key-123",
        output_dimensions=3,
        transport=transport,
        dispatch_policy=MockDispatchPolicy("google"),
        quota_ledger=ledger,
    )

    with pytest.raises(GeneratorExit):
        embedder.embed_texts(["sample text"])

    with open(state_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data.get("active_reservations", {})) == 0
    settled = data.get("settled_requests", [])
    assert len(settled) == 1
    assert settled[0]["success"] is False
    assert settled[0]["error"] == "GeneratorExit"
