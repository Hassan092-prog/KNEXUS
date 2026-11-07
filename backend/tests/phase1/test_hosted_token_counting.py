"""Regressions for hosted token counting, candidate validation, fail-closed dispatch, and canonical API envelopes."""
from __future__ import annotations
import asyncio

import json
import math
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4
import httpx
from pydantic import ValidationError
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_current_actor,
    get_generation_service,
    get_retrieval_service,
    get_token_counter,
)
from app.core.config import Settings, settings
from app.core.database import get_db
from app.core.dispatch_policy import (
    BlockedLiveDispatchPolicy,
    LiveInferenceBlockedError,
    MockDispatchPolicy,
)
from app.core.quota import (
    QuotaConfig,
    QuotaLedger,
    RateLimitExceededError,
)
from app.core.token_counter import (
    GoogleGenAITokenCounter,
    MockTokenCounter,
    TokenCountResult,
    get_default_token_counter,
    validate_token_count_result,
)
from app.main import app
from app.models import Document, DocumentChunk, Embedding, IngestionJob
from app.schemas import ActorContext, EvidenceChunk, GenerationResult
from app.services.ingestion.chunking import (
    ChunkDraft,
    PHYSICAL_MAX_CANDIDATE_CHARS,
    chunk_document,
    chunk_document_with_token_validation,
)
from app.services.ingestion.embedding import GoogleGenAIEmbedder
from app.services.ingestion.errors import (
    EmbeddingUnavailableError,
    InputTokenLimitExceededError,
    TokenCountingError,
    TokenCountingSettlementError,
)
from app.services.ingestion.parsing import ParsedSection
from app.services.ingestion.processor import process_document
from app.services.retrieval.service import RetrievalService


# ==============================================================================
# 1. Exact Unicode and source preservation
# ==============================================================================

def test_unicode_and_exact_source_preservation():
    doc_id = uuid4()
    unicode_text_1 = "?????????? ??????????????! ???? Architecturally preserved curly 'quotes' and em???dash ??? here."
    unicode_text_2 = "????????????, ??????! ???? Special math symbols: ???(x) = ??? y dx."

    sections = [
        ParsedSection(text=unicode_text_1, source_metadata={"file": "test1.pdf"}, page=1),
        ParsedSection(text=unicode_text_2, source_metadata={"file": "test2.pdf"}, page=2),
    ]

    counter = MockTokenCounter(fixed_count=50)
    chunks = chunk_document_with_token_validation(
        doc_id,
        sections,
        counter,
        target_chars=60,
        max_candidate_chars=100,
        overlap_chars=10,
        max_effective_tokens=2048,
    )

    assert len(chunks) >= 2
    for chunk in chunks:
        assert isinstance(chunk.id, UUID)
        assert chunk.token_count == 50
        assert chunk.source_metadata["effective_tokens"] == 58  # 50 + 8
        assert chunk.source_metadata["overhead_tokens"] == 8
        assert (
            chunk.content in unicode_text_1
            or chunk.content in unicode_text_2
            or chunk.content in f"{unicode_text_1}\n\n{unicode_text_2}"
        )


# ==============================================================================
# 2. Proposing candidates locally and splitting oversized without silent truncation
# ==============================================================================

def test_candidate_above_limit_is_split_without_silent_truncation():
    doc_id = uuid4()
    part_a = "First section sentence alpha. " * 5
    part_b = "Second section sentence beta. " * 5
    full_text = f"{part_a}\n\n{part_b}".strip()

    sections = [ParsedSection(text=full_text, source_metadata={}, page=1)]

    class DynamicOversizedCounter:
        def __init__(self):
            self.counted = []

        def count_tokens(self, text, model="gemini-embedding-001", request_type="document", timeout=None):
            self.counted.append(text)
            import hashlib
            h = hashlib.sha256(text.encode("utf-8")).hexdigest()
            raw = 2500 if len(text) > 200 else 100
            return TokenCountResult(
                raw_tokens=raw,
                overhead_tokens=8,
                effective_tokens=raw + 8,
                model_name=model,
                content_hash=h,
                request_type=request_type,
            )

    counter = DynamicOversizedCounter()
    chunks = chunk_document_with_token_validation(
        doc_id,
        sections,
        counter,
        target_chars=350,
        max_candidate_chars=500,
        max_effective_tokens=2048,
    )

    assert len(chunks) >= 2
    for c in chunks:
        assert c.source_metadata["effective_tokens"] <= 2048
    joined_contents = " ".join(c.content for c in chunks)
    assert "First section sentence alpha" in joined_contents
    assert "Second section sentence beta" in joined_contents


def test_indivisible_candidate_above_limit_fails_closed():
    doc_id = uuid4()
    sections = [ParsedSection(text="A", source_metadata={}, page=1)]
    counter = MockTokenCounter(fixed_count=3000, max_allowed_tokens=2048, overhead_tokens=8)

    with pytest.raises(InputTokenLimitExceededError, match="exceeds token limit"):
        chunk_document_with_token_validation(
            doc_id,
            sections,
            counter,
            max_effective_tokens=2048,
        )


def test_query_above_limit_fails_closed():
    counter = MockTokenCounter(fixed_count=2500, max_allowed_tokens=2048, overhead_tokens=8)

    class MockEmbedder:
        model_name = "gemini-embedding-001"
        model_revision = "001"

        def embed_texts(self, texts, **kwargs):
            raise AssertionError("Embedder should not be called when query exceeds token ceiling")

    service = RetrievalService(embedder=MockEmbedder(), token_counter=counter, max_query_tokens=2048)
    actor = ActorContext(org_id=uuid4(), user_id=uuid4(), effective_roles=["employee"])

    class MockSession:
        pass

    with pytest.raises(InputTokenLimitExceededError, match="Query token count .* exceeds maximum"):
        asyncio.run(service.retrieve(MockSession(), actor, "Oversized question", top_k=3))


# ==============================================================================
# 3. Counting Semantics & Correspondence Validation
# ==============================================================================

def test_token_count_result_correspondence_validation():
    sample_text = "Verification of counting result correspondence"
    import hashlib
    valid_hash = hashlib.sha256(sample_text.encode("utf-8")).hexdigest()

    valid_result = TokenCountResult(
        raw_tokens=100,
        overhead_tokens=8,
        effective_tokens=108,
        model_name="gemini-embedding-001",
        content_hash=valid_hash,
        request_type="document",
    )
    validate_token_count_result(
        valid_result,
        expected_model="gemini-embedding-001",
        expected_text=sample_text,
        expected_request_type="document",
    )

    with pytest.raises(TokenCountingError, match="Model mismatch"):
        validate_token_count_result(
            valid_result,
            expected_model="other-model",
            expected_text=sample_text,
            expected_request_type="document",
        )

    with pytest.raises(TokenCountingError, match="Content hash mismatch"):
        validate_token_count_result(
            valid_result,
            expected_model="gemini-embedding-001",
            expected_text="Different text content",
            expected_request_type="document",
        )

    with pytest.raises(TokenCountingError, match="Request type mismatch"):
        validate_token_count_result(
            valid_result,
            expected_model="gemini-embedding-001",
            expected_text=sample_text,
            expected_request_type="query",
        )

    bool_raw = TokenCountResult(
        raw_tokens=True,  # type: ignore
        overhead_tokens=8,
        effective_tokens=9,
        model_name="gemini-embedding-001",
        content_hash=valid_hash,
        request_type="document",
    )
    with pytest.raises(TokenCountingError, match="invalid raw_tokens"):
        validate_token_count_result(
            bool_raw,
            expected_model="gemini-embedding-001",
            expected_text=sample_text,
            expected_request_type="document",
        )

    neg_raw = TokenCountResult(
        raw_tokens=-10,
        overhead_tokens=8,
        effective_tokens=-2,
        model_name="gemini-embedding-001",
        content_hash=valid_hash,
        request_type="document",
    )
    with pytest.raises(TokenCountingError, match="invalid raw_tokens"):
        validate_token_count_result(
            neg_raw,
            expected_model="gemini-embedding-001",
            expected_text=sample_text,
            expected_request_type="document",
        )

    inconsistent = TokenCountResult(
        raw_tokens=100,
        overhead_tokens=8,
        effective_tokens=120,
        model_name="gemini-embedding-001",
        content_hash=valid_hash,
        request_type="document",
    )
    with pytest.raises(TokenCountingError, match="mathematically inconsistent"):
        validate_token_count_result(
            inconsistent,
            expected_model="gemini-embedding-001",
            expected_text=sample_text,
            expected_request_type="document",
        )


def test_single_overhead_evaluation_no_double_subtraction():
    doc_id = uuid4()
    sections = [ParsedSection(text="Valid document within approved ceiling.", source_metadata={}, page=1)]
    counter = MockTokenCounter(fixed_count=2040, overhead_tokens=8, max_allowed_tokens=2048)

    chunks = chunk_document_with_token_validation(
        doc_id,
        sections,
        counter,
        max_effective_tokens=2048,
    )
    assert len(chunks) == 1
    assert chunks[0].source_metadata["effective_tokens"] == 2048
    assert chunks[0].token_count == 2040


# ==============================================================================
# 4. Bounded External Counting Work & Monotonic Deadline Enforcement
# ==============================================================================

def test_validation_call_allowance_exhaustion_fails_closed():
    doc_id = uuid4()
    sections = [ParsedSection(text="Sentence word. " * 300, source_metadata={}, page=1)]

    class SplittingCounter:
        def __init__(self):
            self.calls = 0

        def count_tokens(self, text, model="gemini-embedding-001", request_type="document", timeout=None):
            self.calls += 1
            import hashlib
            h = hashlib.sha256(text.encode("utf-8")).hexdigest()
            raw = 2500 if len(text) > 50 else 10
            return TokenCountResult(raw, 8, raw + 8, model, h, request_type)

    counter = SplittingCounter()
    with pytest.raises(TokenCountingError, match="call allowance of 3 exceeded"):
        chunk_document_with_token_validation(
            doc_id,
            sections,
            counter,
            max_validation_calls=3,
        )


def test_deadline_exceeded_before_counting_fails_closed():
    doc_id = uuid4()
    sections = [ParsedSection(text="Some text", source_metadata={}, page=1)]
    counter = MockTokenCounter(fixed_count=50)

    # Clock stepping: 0.0 at function start, advances to 1.5s (> 1.0s deadline) before counting begins
    times = [0.0, 1.5]
    mock_clock = lambda: times.pop(0) if times else 1.5

    with pytest.raises(TokenCountingError, match="deadline of 1.0s exceeded"):
        chunk_document_with_token_validation(
            doc_id,
            sections,
            counter,
            deadline_seconds=1.0,
            clock=mock_clock,
        )
    assert len(counter.counted_calls) == 0


def test_deterministic_late_counting_result_rejected_and_embedding_receives_zero_calls():
    """Deterministic regression:

    - Deadline: 1 second.
    - Mock count finishes at 2 seconds.
    - Validation fails and embedding receives zero calls.
    """
    clock_time = 0.0

    def mock_clock():
        nonlocal clock_time
        return clock_time

    def advance_time_to_2_seconds():
        nonlocal clock_time
        clock_time = 2.0

    counter = MockTokenCounter(
        fixed_count=50,
        deadline_seconds=1.0,
        clock=mock_clock,
        time_advance_callback=advance_time_to_2_seconds,
    )

    doc_id = uuid4()
    sections = [ParsedSection(text="Text that completes late", source_metadata={}, page=1)]

    # 1. Direct validation failure: post-count check must strictly reject the late result
    with pytest.raises(TokenCountingError, match="deadline of 1.0s exceeded"):
        chunk_document_with_token_validation(
            doc_id,
            sections,
            counter,
            deadline_seconds=1.0,
            clock=mock_clock,
        )

    # 2. Pipeline integration: process_document must fail and embedding receives ZERO calls
    clock_time = 0.0
    embedder_calls = []
    pipeline_counter = MockTokenCounter(
        fixed_count=50,
        deadline_seconds=1.0,
        clock=mock_clock,
        time_advance_callback=advance_time_to_2_seconds,
    )

    class MockTrackingEmbedder:
        model_name = "gemini-embedding-001"
        model_revision = "001"

        def embed_texts(self, texts, **kwargs):
            embedder_calls.append(texts)
            return [[0.1] * 384]

    org_id = uuid4()
    doc = Document(
        id=doc_id, org_id=org_id, uploaded_by=uuid4(), title="Doc",
        source_type="docx", storage_key="k", status="queued",
        allowed_roles=["employee"], chunk_count=0
    )
    job = IngestionJob(id=uuid4(), org_id=org_id, document_id=doc_id, attempt_number=1, status="queued")

    class MockSession:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, *args): return doc
        async def execute(self, *args):
            class S:
                def scalar_one_or_none(self): return job
            return S()
        def add(self, item): pass
        async def flush(self): pass
        async def commit(self): pass

    success = asyncio.run(
        process_document(
            doc_id,
            parsed_sections=sections,
            session_factory=lambda: MockSession(),
            embedder=MockTrackingEmbedder(),
            token_counter=pipeline_counter,
        )
    )

    assert success is False
    assert job.status == "failed"
    assert len(embedder_calls) == 0


def test_exact_deadline_boundary_fails_closed():
    doc_id = uuid4()
    sections = [ParsedSection(text="Boundary candidate", source_metadata={}, page=1)]

    # Pre-count exact boundary: clock is 0.0 at start, reaches 1.0 (exact deadline) before counting
    pre_times = [0.0, 1.0]
    pre_clock = lambda: pre_times.pop(0) if pre_times else 1.0
    counter = MockTokenCounter(fixed_count=50)

    with pytest.raises(TokenCountingError, match="deadline of 1.0s exceeded"):
        chunk_document_with_token_validation(
            doc_id,
            sections,
            counter,
            deadline_seconds=1.0,
            clock=pre_clock,
        )

    # Post-count exact boundary: starts at 0.0, advances to exactly 1.0 during count
    clock_time = 0.0

    def mock_clock():
        nonlocal clock_time
        return clock_time

    def advance_to_exact_deadline():
        nonlocal clock_time
        clock_time = 1.0

    boundary_counter = MockTokenCounter(
        fixed_count=50,
        time_advance_callback=advance_to_exact_deadline,
    )
    with pytest.raises(TokenCountingError, match="deadline of 1.0s exceeded"):
        chunk_document_with_token_validation(
            doc_id,
            sections,
            boundary_counter,
            deadline_seconds=1.0,
            clock=mock_clock,
        )


def test_oversized_candidate_split_exhausts_shared_deadline():
    doc_id = uuid4()
    # Content requiring repeated splits
    sections = [ParsedSection(text="Part 1. Part 2. Part 3. Part 4. Part 5.", source_metadata={}, page=1)]

    clock_time = 0.0

    def mock_clock():
        nonlocal clock_time
        return clock_time

    class TimeSteppingSplittingCounter:
        def __init__(self):
            self.calls = 0

        def count_tokens(self, text, model="gemini-embedding-001", request_type="document", timeout=None):
            nonlocal clock_time
            self.calls += 1
            clock_time += 1.0  # Each validation call consumes 1 second
            import hashlib
            h = hashlib.sha256(text.encode("utf-8")).hexdigest()
            # Oversized until text is short
            raw = 2500 if len(text) > 10 else 10
            return TokenCountResult(raw, 8, raw + 8, model, h, request_type)

    counter = TimeSteppingSplittingCounter()
    # Shared deadline of 2.5s allows at most 2 calls before exhaustion
    with pytest.raises(TokenCountingError, match="deadline of 2.5s exceeded"):
        chunk_document_with_token_validation(
            doc_id,
            sections,
            counter,
            deadline_seconds=2.5,
            clock=mock_clock,
        )
    assert counter.calls >= 2


def test_remaining_allowance_passed_into_supported_counter():
    doc_id = uuid4()
    sections = [ParsedSection(text="Sample content", source_metadata={}, page=1)]

    times = [0.0, 2.0, 2.0]
    mock_clock = lambda: times.pop(0) if times else 2.0

    counter = MockTokenCounter(fixed_count=50)

    # Clock at 2.0s with deadline 10.0s -> remaining allowance passed into counter must be 8.0s
    chunk_document_with_token_validation(
        doc_id,
        sections,
        counter,
        deadline_seconds=10.0,
        clock=mock_clock,
    )
    assert counter.last_timeout is not None
    assert math.isclose(counter.last_timeout, 8.0, rel_tol=1e-5)
    assert len(counter.counted_calls) == 1


def test_finite_positive_timeout_and_deadline_settings_validated():
    # 1. Settings validation rejects zero, negative, NaN, Inf, and booleans
    with pytest.raises(ValidationError):
        Settings(EMBEDDING_TIMEOUT=0)

    with pytest.raises(ValidationError):
        Settings(EMBEDDING_TIMEOUT=-5.0)

    with pytest.raises(ValidationError):
        Settings(EMBEDDING_TIMEOUT=float("nan"))

    with pytest.raises(ValidationError):
        Settings(EMBEDDING_TIMEOUT=float("inf"))

    with pytest.raises(ValidationError):
        Settings(EMBEDDING_VALIDATION_DEADLINE_SECONDS=0)

    with pytest.raises(ValidationError):
        Settings(EMBEDDING_VALIDATION_DEADLINE_SECONDS=-1.0)

    with pytest.raises(ValidationError):
        Settings(EMBEDDING_VALIDATION_DEADLINE_SECONDS=float("nan"))

    # 2. GoogleGenAITokenCounter rejects invalid timeout
    with pytest.raises(ValueError, match="timeout must be a finite positive number"):
        GoogleGenAITokenCounter(timeout=0)

    with pytest.raises(ValueError, match="timeout must be a finite positive number"):
        GoogleGenAITokenCounter(timeout=-1.0)

    with pytest.raises(ValueError, match="timeout must be a finite positive number"):
        GoogleGenAITokenCounter(timeout=float("nan"))

    with pytest.raises(ValueError, match="timeout must be a finite positive number"):
        GoogleGenAITokenCounter(timeout=float("inf"))

    # 3. chunk_document_with_token_validation rejects invalid deadline
    doc_id = uuid4()
    sections = [ParsedSection(text="Test", source_metadata={}, page=1)]
    counter = MockTokenCounter(fixed_count=10)

    with pytest.raises(ValueError, match="deadline_seconds must be a finite positive number"):
        chunk_document_with_token_validation(doc_id, sections, counter, deadline_seconds=0)

    with pytest.raises(ValueError, match="deadline_seconds must be a finite positive number"):
        chunk_document_with_token_validation(doc_id, sections, counter, deadline_seconds=-2.0)

    with pytest.raises(ValueError, match="deadline_seconds must be a finite positive number"):
        chunk_document_with_token_validation(doc_id, sections, counter, deadline_seconds=float("nan"))


def test_physical_size_guard_boundary():
    assert PHYSICAL_MAX_CANDIDATE_CHARS == 8000


# ==============================================================================
# 5. Counter Failures & Secret Sanitization
# ==============================================================================

def test_google_token_counter_http_error_sanitized(tmp_path: Path):
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=tmp_path / "ledger.json"))
    transport = httpx.MockTransport(lambda req: httpx.Response(500, text="Internal Server Error"))
    counter = GoogleGenAITokenCounter(
        api_key="test-key",
        transport=transport,
        dispatch_policy=MockDispatchPolicy(),
        quota_ledger=ledger,
    )
    with pytest.raises(TokenCountingError, match="Google countTokens failed with HTTP status 500"):
        counter.count_tokens("Test text", model="gemini-embedding-001")


def test_google_token_counter_malformed_json_sanitized(tmp_path: Path):
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=tmp_path / "ledger.json"))
    transport = httpx.MockTransport(lambda req: httpx.Response(200, text="not json {"))
    counter = GoogleGenAITokenCounter(
        api_key="test-key",
        transport=transport,
        dispatch_policy=MockDispatchPolicy(),
        quota_ledger=ledger,
    )
    with pytest.raises(TokenCountingError, match="Google countTokens returned malformed JSON payload"):
        counter.count_tokens("Test text", model="gemini-embedding-001")


def test_google_token_counter_missing_total_tokens_sanitized(tmp_path: Path):
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=tmp_path / "ledger.json"))
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={"other": 123}))
    counter = GoogleGenAITokenCounter(
        api_key="test-key",
        transport=transport,
        dispatch_policy=MockDispatchPolicy(),
        quota_ledger=ledger,
    )
    with pytest.raises(TokenCountingError, match="Google countTokens response missing 'totalTokens' field"):
        counter.count_tokens("Test text", model="gemini-embedding-001")


def test_google_token_counter_rejects_boolean_total_tokens(tmp_path: Path):
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=tmp_path / "ledger.json"))
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={"totalTokens": True}))
    counter = GoogleGenAITokenCounter(
        api_key="test-key",
        transport=transport,
        dispatch_policy=MockDispatchPolicy(),
        quota_ledger=ledger,
    )
    with pytest.raises(TokenCountingError, match="Google countTokens returned non-integer or negative token count"):
        counter.count_tokens("Test text", model="gemini-embedding-001")


def test_google_token_counter_rejects_negative_total_tokens(tmp_path: Path):
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=tmp_path / "ledger.json"))
    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={"totalTokens": -5}))
    counter = GoogleGenAITokenCounter(
        api_key="test-key",
        transport=transport,
        dispatch_policy=MockDispatchPolicy(),
        quota_ledger=ledger,
    )
    with pytest.raises(TokenCountingError, match="Google countTokens returned non-integer or negative token count"):
        counter.count_tokens("Test text", model="gemini-embedding-001")


def test_google_token_counter_timeout(tmp_path: Path):
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=tmp_path / "ledger.json"))
    def timeout_handler(req):
        raise httpx.TimeoutException("Connection timed out")

    transport = httpx.MockTransport(timeout_handler)
    counter = GoogleGenAITokenCounter(
        api_key="test-key",
        transport=transport,
        dispatch_policy=MockDispatchPolicy(),
        quota_ledger=ledger,
    )
    with pytest.raises(TokenCountingError, match="Google countTokens request timed out"):
        counter.count_tokens("Test text", model="gemini-embedding-001")


def test_secret_sanitization_does_not_leak_keys_or_payloads():
    secret_key = "AIzaSyFakeSecretKeyThatMustNotLeak"
    auth_header = "Bearer super-secret-internal-token-12345"

    def leak_attempt(req):
        return httpx.Response(
            500,
            text=f'{{"error": "Failed with secret key {secret_key}", "header": "{auth_header}"}}',
        )

    transport = httpx.MockTransport(leak_attempt)
    counter = GoogleGenAITokenCounter(
        api_key=secret_key,
        transport=transport,
        dispatch_policy=MockDispatchPolicy(),
    )
    try:
        counter.count_tokens("Secret text", model="gemini-embedding-001")
        pytest.fail("Should have raised TokenCountingError")
    except TokenCountingError as exc:
        msg = str(exc)
        repr_msg = repr(exc)
        assert secret_key not in msg
        assert auth_header not in msg
        assert secret_key not in repr_msg
        assert auth_header not in repr_msg


# ==============================================================================
# 6. Real QuotaLedger Integration & Settlement Failure Propagation
# ==============================================================================

def test_real_quota_ledger_success(tmp_path: Path):
    state_file = tmp_path / "ledger.json"
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=state_file))

    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={"totalTokens": 42}))
    counter = GoogleGenAITokenCounter(
        model_name="gemini-embedding-001",
        api_key="test-key",
        transport=transport,
        dispatch_policy=MockDispatchPolicy(),
        quota_ledger=ledger,
    )

    res = counter.count_tokens("Input text for ledger success test", model="gemini-embedding-001")
    assert res.raw_tokens == 42
    assert res.effective_tokens == 50

    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert len(state["active_reservations"]) == 0
    assert len(state["settled_requests"]) == 1
    record = state["settled_requests"][0]
    assert record["scope"] == "google:gemini-embedding-001"
    assert record["provider"] == "google"
    assert record["model"] == "gemini-embedding-001"
    assert record["status_code"] == 200
    assert record["success"] is True
    assert record["tokens_unresolved"] is True
    assert record["usage"] is None


def test_real_quota_ledger_timeout(tmp_path: Path):
    state_file = tmp_path / "ledger.json"
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=state_file))

    def timeout_fn(req):
        raise httpx.TimeoutException("Timeout")

    transport = httpx.MockTransport(timeout_fn)
    counter = GoogleGenAITokenCounter(
        model_name="gemini-embedding-001",
        api_key="test-key",
        transport=transport,
        dispatch_policy=MockDispatchPolicy(),
        quota_ledger=ledger,
    )

    with pytest.raises(TokenCountingError, match="timed out"):
        counter.count_tokens("Text", model="gemini-embedding-001")

    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert len(state["active_reservations"]) == 0
    assert len(state["settled_requests"]) == 1
    record = state["settled_requests"][0]
    assert record["success"] is False
    assert record["error"] == "timeout"
    assert record["tokens_unresolved"] is True


def test_real_quota_ledger_malformed_response(tmp_path: Path):
    state_file = tmp_path / "ledger.json"
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=state_file))

    transport = httpx.MockTransport(lambda req: httpx.Response(200, json={"bad": "data"}))
    counter = GoogleGenAITokenCounter(
        model_name="gemini-embedding-001",
        api_key="test-key",
        transport=transport,
        dispatch_policy=MockDispatchPolicy(),
        quota_ledger=ledger,
    )

    with pytest.raises(TokenCountingError, match="missing 'totalTokens'"):
        counter.count_tokens("Text", model="gemini-embedding-001")

    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert len(state["active_reservations"]) == 0
    assert len(state["settled_requests"]) == 1
    record = state["settled_requests"][0]
    assert record["success"] is False
    assert record["error"] == "missing_total_tokens"


def test_real_quota_ledger_http_429(tmp_path: Path):
    state_file = tmp_path / "ledger.json"
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=state_file))

    transport = httpx.MockTransport(lambda req: httpx.Response(429, text="Too Many Requests"))
    counter = GoogleGenAITokenCounter(
        model_name="gemini-embedding-001",
        api_key="test-key",
        transport=transport,
        dispatch_policy=MockDispatchPolicy(),
        quota_ledger=ledger,
    )

    with pytest.raises(TokenCountingError, match="HTTP status 429"):
        counter.count_tokens("Text", model="gemini-embedding-001")

    state = json.loads(state_file.read_text(encoding="utf-8"))
    scope_info = state["scopes"]["google:gemini-embedding-001"]
    assert scope_info["rate_limited"] is True

    with pytest.raises(RateLimitExceededError, match="rate limit active"):
        ledger.reserve_attempt("google", "gemini-embedding-001")


def test_settlement_failure_on_successful_provider_response(tmp_path: Path, monkeypatch):
    """Settlement failure on provider success propagates TokenCountingSettlementError

    and retains the outstanding reservation in the ledger. Exactly 1 provider call made.
    """
    state_file = tmp_path / "ledger.json"
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=state_file))

    provider_calls = 0

    def mock_resp(req):
        nonlocal provider_calls
        provider_calls += 1
        return httpx.Response(200, json={"totalTokens": 42})

    counter = GoogleGenAITokenCounter(
        model_name="gemini-embedding-001",
        api_key="test-key",
        transport=httpx.MockTransport(mock_resp),
        dispatch_policy=MockDispatchPolicy(),
        quota_ledger=ledger,
    )

    def failing_settle(*args, **kwargs):
        raise OSError("Disk write failed during settlement")

    monkeypatch.setattr(ledger, "settle_attempt", failing_settle)

    with pytest.raises(TokenCountingSettlementError) as exc_info:
        counter.count_tokens("Input text", model="gemini-embedding-001")

    assert "Quota settlement failed (OSError)" in str(exc_info.value)
    assert "outstanding reservation preserved" in str(exc_info.value)
    assert exc_info.value.provider_error is None
    assert exc_info.value.status_code == 200

    # Exactly one provider call made; no retry
    assert provider_calls == 1

    # Outstanding accounting preserved in state file
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert len(state["active_reservations"]) == 1


def test_settlement_failure_on_timeout_provider_response(tmp_path: Path, monkeypatch):
    """Settlement failure on timeout propagates TokenCountingSettlementError

    preserving safe 'timeout' classification and retained reservation. Exactly 1 call.
    """
    state_file = tmp_path / "ledger.json"
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=state_file))

    provider_calls = 0

    def timeout_transport(req):
        nonlocal provider_calls
        provider_calls += 1
        raise httpx.TimeoutException("Network socket timeout")

    counter = GoogleGenAITokenCounter(
        model_name="gemini-embedding-001",
        api_key="test-key",
        transport=httpx.MockTransport(timeout_transport),
        dispatch_policy=MockDispatchPolicy(),
        quota_ledger=ledger,
    )

    monkeypatch.setattr(ledger, "settle_attempt", lambda *a, **k: (_ for _ in ()).throw(OSError("Disk failure")))

    with pytest.raises(TokenCountingSettlementError) as exc_info:
        counter.count_tokens("Input text", model="gemini-embedding-001")

    assert "Quota settlement failed (OSError)" in str(exc_info.value)
    assert "Original provider failure: Google countTokens request timed out." in str(exc_info.value)
    assert exc_info.value.provider_error == "timeout"
    assert exc_info.value.status_code is None

    assert provider_calls == 1
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert len(state["active_reservations"]) == 1


def test_settlement_failure_on_http_429_provider_response(tmp_path: Path, monkeypatch):
    """Settlement failure on HTTP 429 propagates TokenCountingSettlementError

    preserving status_code=429 and error='http_429'. Exactly 1 call.
    """
    state_file = tmp_path / "ledger.json"
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=state_file))

    provider_calls = 0

    def rate_limit_transport(req):
        nonlocal provider_calls
        provider_calls += 1
        return httpx.Response(429, text="Too Many Requests")

    counter = GoogleGenAITokenCounter(
        model_name="gemini-embedding-001",
        api_key="test-key",
        transport=httpx.MockTransport(rate_limit_transport),
        dispatch_policy=MockDispatchPolicy(),
        quota_ledger=ledger,
    )

    monkeypatch.setattr(ledger, "settle_attempt", lambda *a, **k: (_ for _ in ()).throw(OSError("I/O error")))

    with pytest.raises(TokenCountingSettlementError) as exc_info:
        counter.count_tokens("Input text", model="gemini-embedding-001")

    assert "Quota settlement failed (OSError)" in str(exc_info.value)
    assert "429" in str(exc_info.value)
    assert exc_info.value.status_code == 429
    assert exc_info.value.provider_error == "http_429"

    assert provider_calls == 1
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert len(state["active_reservations"]) == 1


def test_settlement_failure_on_malformed_json_provider_response(tmp_path: Path, monkeypatch):
    """Settlement failure on malformed JSON propagates TokenCountingSettlementError."""
    state_file = tmp_path / "ledger.json"
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=state_file))

    provider_calls = 0

    def malformed_transport(req):
        nonlocal provider_calls
        provider_calls += 1
        return httpx.Response(200, text="not valid json {")

    counter = GoogleGenAITokenCounter(
        model_name="gemini-embedding-001",
        api_key="test-key",
        transport=httpx.MockTransport(malformed_transport),
        dispatch_policy=MockDispatchPolicy(),
        quota_ledger=ledger,
    )

    monkeypatch.setattr(ledger, "settle_attempt", lambda *a, **k: (_ for _ in ()).throw(OSError("Disk failure")))

    with pytest.raises(TokenCountingSettlementError) as exc_info:
        counter.count_tokens("Input text", model="gemini-embedding-001")

    assert "Quota settlement failed (OSError)" in str(exc_info.value)
    assert "malformed JSON payload" in str(exc_info.value)
    assert exc_info.value.provider_error == "malformed_json"
    assert provider_calls == 1
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert len(state["active_reservations"]) == 1


def test_settlement_failure_on_invalid_count_provider_response(tmp_path: Path, monkeypatch):
    """Settlement failure on invalid totalTokens propagates TokenCountingSettlementError."""
    state_file = tmp_path / "ledger.json"
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=state_file))

    provider_calls = 0

    def invalid_count_transport(req):
        nonlocal provider_calls
        provider_calls += 1
        return httpx.Response(200, json={"totalTokens": -10})

    counter = GoogleGenAITokenCounter(
        model_name="gemini-embedding-001",
        api_key="test-key",
        transport=httpx.MockTransport(invalid_count_transport),
        dispatch_policy=MockDispatchPolicy(),
        quota_ledger=ledger,
    )

    monkeypatch.setattr(ledger, "settle_attempt", lambda *a, **k: (_ for _ in ()).throw(OSError("Disk failure")))

    with pytest.raises(TokenCountingSettlementError) as exc_info:
        counter.count_tokens("Input text", model="gemini-embedding-001")

    assert "Quota settlement failed (OSError)" in str(exc_info.value)
    assert "invalid_total_tokens" == exc_info.value.provider_error
    assert provider_calls == 1
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert len(state["active_reservations"]) == 1


# ==============================================================================
# 7. Fail-Closed Ingestion & Dispatch Checks
# ==============================================================================

@pytest.mark.asyncio
async def test_no_embedding_dispatch_when_ingestion_counting_fails():
    embedder_calls = []

    class MockTrackingEmbedder:
        model_name = "gemini-embedding-001"
        model_revision = "001"

        def embed_texts(self, texts, **kwargs):
            embedder_calls.append(texts)
            return [[0.1] * 384]

    counter = MockTokenCounter(error_to_raise=TokenCountingError("Network down"))
    embedder = MockTrackingEmbedder()

    doc_id = uuid4()
    org_id = uuid4()
    doc = Document(
        id=doc_id,
        org_id=org_id,
        uploaded_by=uuid4(),
        title="Doc",
        source_type="pdf",
        original_filename="doc.pdf",
        file_size_bytes=100,
        allowed_roles=["employee"],
        status="queued",
    )
    job = IngestionJob(
        id=uuid4(),
        org_id=org_id,
        document_id=doc_id,
        attempt_number=1,
        status="queued",
    )

    class MockSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

        async def get(self, model, ident):
            if model == Document:
                return doc
            return None

        async def execute(self, stmt):
            class ScalarRes:
                def scalar_one_or_none(self):
                    return job

            return ScalarRes()

        async def commit(self):
            pass

    success = await process_document(
        doc_id,
        parsed_sections=[ParsedSection(text="Some text", source_metadata={}, page=1)],
        session_factory=lambda: MockSession(),
        embedder=embedder,
        token_counter=counter,
    )

    assert success is False
    assert job.status == "failed"
    assert len(embedder_calls) == 0


@pytest.mark.asyncio
async def test_no_embedding_dispatch_when_query_counting_fails():
    embedder_calls = []

    class MockTrackingEmbedder:
        model_name = "gemini-embedding-001"
        model_revision = "001"

        def embed_texts(self, texts, **kwargs):
            embedder_calls.append(texts)
            return [[0.1] * 384]

    counter = MockTokenCounter(error_to_raise=TokenCountingError("Counting service unavailable"))
    service = RetrievalService(embedder=MockTrackingEmbedder(), token_counter=counter)

    actor = ActorContext(org_id=uuid4(), user_id=uuid4(), effective_roles=["employee"])

    class MockSession:
        pass

    with pytest.raises(TokenCountingError, match="Counting service unavailable"):
        await service.retrieve(MockSession(), actor, "Question?", top_k=3)

    assert len(embedder_calls) == 0


def test_document_and_query_validation_cache_semantics():
    counter = MockTokenCounter(token_multiplier=0.2)
    text = "Shared query or doc text content"

    res_doc = counter.count_tokens(text, model="gemini-embedding-001", request_type="document")
    res_query = counter.count_tokens(text, model="gemini-embedding-001", request_type="query")

    assert res_doc.request_type == "document"
    assert res_query.request_type == "query"
    assert len(counter.counted_calls) == 2

    res_doc_2 = counter.count_tokens(text, model="gemini-embedding-001", request_type="document")
    assert len(counter.counted_calls) == 2
    assert res_doc_2 == res_doc


def test_counting_failure_no_retries(tmp_path: Path):
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=tmp_path / "ledger.json"))
    counter_calls = 0

    def mock_failure(req):
        nonlocal counter_calls
        counter_calls += 1
        return httpx.Response(503, text="Service Unavailable")

    transport = httpx.MockTransport(mock_failure)
    counter = GoogleGenAITokenCounter(
        api_key="test-key",
        transport=transport,
        dispatch_policy=MockDispatchPolicy(),
        quota_ledger=ledger,
    )

    with pytest.raises(TokenCountingError):
        counter.count_tokens("Test text", model="gemini-embedding-001")

    assert counter_calls == 1


def test_counter_internal_type_error_not_caught_or_retried():
    """Regression:

    - max_validation_calls=1.
    - Counter records its invocation, then raises TypeError("internal timeout accounting failure").
    - Assert exactly one invocation.
    - Assert the error propagates.
    - No accepted chunks and no embedding dispatch.
    """
    invocations = []

    class InternalTypeErrorCounter:
        model_name = "gemini-embedding-001"

        def count_tokens(
            self,
            text: str,
            *,
            model: str = "gemini-embedding-001",
            request_type: str = "document",
            timeout: float | None = None,
        ) -> TokenCountResult:
            invocations.append((text, model, request_type, timeout))
            raise TypeError("internal timeout accounting failure")

    counter = InternalTypeErrorCounter()
    doc_id = uuid4()
    sections = [ParsedSection(text="Test content for internal error", source_metadata={}, page=1)]

    # 1. Direct chunking invocation: raises TypeError immediately, exactly one invocation, never retried
    with pytest.raises(TypeError, match="internal timeout accounting failure"):
        chunk_document_with_token_validation(
            doc_id,
            sections,
            counter,
            max_validation_calls=1,
        )

    assert len(invocations) == 1
    # Verify supported timeout argument receives the remaining allowance without retry
    assert invocations[0][3] is not None
    assert invocations[0][3] > 0

    # 2. Pipeline integration: process_document fails and embedding receives zero calls
    invocations.clear()
    embedder_calls = []

    class MockTrackingEmbedder:
        model_name = "gemini-embedding-001"
        model_revision = "001"

        def embed_texts(self, texts, **kwargs):
            embedder_calls.append(texts)
            return [[0.1] * 384]

    org_id = uuid4()
    doc = Document(
        id=doc_id, org_id=org_id, uploaded_by=uuid4(), title="Doc",
        source_type="docx", storage_key="k", status="queued",
        allowed_roles=["employee"], chunk_count=0
    )
    job = IngestionJob(id=uuid4(), org_id=org_id, document_id=doc_id, attempt_number=1, status="queued")

    class MockSession:
        async def __aenter__(self): return self
        async def __aexit__(self, *args): pass
        async def get(self, *args): return doc
        async def execute(self, *args):
            class S:
                def scalar_one_or_none(self): return job
            return S()
        def add(self, item): pass
        async def flush(self): pass
        async def commit(self): pass

    success = asyncio.run(
        process_document(
            doc_id,
            parsed_sections=sections,
            session_factory=lambda: MockSession(),
            embedder=MockTrackingEmbedder(),
            token_counter=counter,
        )
    )

    assert success is False
    assert job.status == "failed"
    assert len(invocations) == 1
    assert len(embedder_calls) == 0


def test_unsupported_timeout_argument_determined_before_invocation_without_retry():
    """If counter does not accept timeout, argument support is determined before invocation, not via exception retry."""
    invocations = []

    class LegacyNoTimeoutCounter:
        model_name = "gemini-embedding-001"

        def count_tokens(self, text: str, *, model: str = "gemini-embedding-001", request_type: str = "document") -> TokenCountResult:
            invocations.append((text, model, request_type))
            import hashlib
            h = hashlib.sha256(text.encode("utf-8")).hexdigest()
            return TokenCountResult(50, 8, 58, model, h, request_type)

    counter = LegacyNoTimeoutCounter()
    doc_id = uuid4()
    sections = [ParsedSection(text="Legacy test content", source_metadata={}, page=1)]

    chunks = chunk_document_with_token_validation(
        doc_id,
        sections,
        counter,
        max_validation_calls=1,
    )

    assert len(chunks) == 1
    assert len(invocations) == 1


def test_default_dispatch_blocked_for_counting():
    counter = GoogleGenAITokenCounter(
        api_key="test-key",
        dispatch_policy=BlockedLiveDispatchPolicy(),
    )
    with pytest.raises(LiveInferenceBlockedError, match="Live dispatch to provider 'google'"):
        counter.count_tokens("Some text", model="gemini-embedding-001")


def test_default_dispatch_blocked_for_embedding():
    embedder = GoogleGenAIEmbedder(
        api_key="test-key",
        dispatch_policy=BlockedLiveDispatchPolicy(),
    )
    with pytest.raises(LiveInferenceBlockedError, match="Live dispatch to provider 'google'"):
        embedder.embed_texts(["Some text"])


# ==============================================================================
# 8. ASGI Query Route Tests with TestClient(app)
# ==============================================================================

class MockQueryTrackingSession:
    async def execute(self, *args, **kwargs):
        class EmptyRes:
            def scalars(self):
                return self

            def all(self):
                return []

        return EmptyRes()


def test_asgi_query_route_oversized_query_returns_422():
    embedder_called = False
    generator_called = False

    class TrackingEmbedder:
        model_name = "gemini-embedding-001"
        model_revision = "001"

        def embed_texts(self, texts, **kwargs):
            nonlocal embedder_called
            embedder_called = True
            return [[0.1] * 384]

    class TrackingGenerator:
        model = "fake"
        provider = "fake"

        async def generate(self, *args, **kwargs):
            nonlocal generator_called
            generator_called = True
            return GenerationResult(answer="A", cited_ids=[], abstained=False, abstention_reason=None)

    counter = MockTokenCounter(fixed_count=2500, max_allowed_tokens=2048, overhead_tokens=8)
    retrieval_svc = RetrievalService(embedder=TrackingEmbedder(), token_counter=counter, max_query_tokens=2048)

    app.dependency_overrides[get_retrieval_service] = lambda: retrieval_svc
    app.dependency_overrides[get_generation_service] = lambda: TrackingGenerator()
    app.dependency_overrides[get_db] = lambda: MockQueryTrackingSession()
    app.dependency_overrides[get_current_actor] = lambda: ActorContext(
        org_id=uuid4(), user_id=uuid4(), effective_roles=["employee"]
    )

    try:
        with TestClient(app) as client:
            resp = client.post("/api/v1/query", json={"question": "What is the policy?"})
            assert resp.status_code == 422
            body = resp.json()
            assert body["code"] == "VALIDATION_ERROR"
            assert body["detail"] == "The submitted query exceeds the maximum allowed input token limit."
            assert "request_id" in body
            assert UUID(body["request_id"])
            assert resp.headers.get("x-request-id") == body["request_id"]
            assert embedder_called is False
            assert generator_called is False
    finally:
        app.dependency_overrides.clear()


def test_asgi_query_route_counter_failure_returns_503():
    embedder_called = False
    generator_called = False

    class TrackingEmbedder:
        model_name = "gemini-embedding-001"
        model_revision = "001"

        def embed_texts(self, texts, **kwargs):
            nonlocal embedder_called
            embedder_called = True
            return [[0.1] * 384]

    class TrackingGenerator:
        model = "fake"
        provider = "fake"

        async def generate(self, *args, **kwargs):
            nonlocal generator_called
            generator_called = True
            return GenerationResult(answer="A", cited_ids=[], abstained=False, abstention_reason=None)

    counter = MockTokenCounter(error_to_raise=TokenCountingError("Token count endpoint unreachable"))
    retrieval_svc = RetrievalService(embedder=TrackingEmbedder(), token_counter=counter)

    app.dependency_overrides[get_retrieval_service] = lambda: retrieval_svc
    app.dependency_overrides[get_generation_service] = lambda: TrackingGenerator()
    app.dependency_overrides[get_db] = lambda: MockQueryTrackingSession()
    app.dependency_overrides[get_current_actor] = lambda: ActorContext(
        org_id=uuid4(), user_id=uuid4(), effective_roles=["employee"]
    )

    try:
        with TestClient(app) as client:
            resp = client.post("/api/v1/query", json={"question": "What is the policy?"})
            assert resp.status_code == 503
            body = resp.json()
            assert body["code"] == "PROVIDER_UNAVAILABLE"
            assert body["detail"] == "The configured embedding service is unavailable."
            assert "request_id" in body
            assert UUID(body["request_id"])
            assert resp.headers.get("x-request-id") == body["request_id"]
            assert embedder_called is False
            assert generator_called is False
    finally:
        app.dependency_overrides.clear()


def test_asgi_query_route_blocked_live_dispatch_returns_503():
    embedder_called = False
    generator_called = False

    class TrackingEmbedder:
        model_name = "gemini-embedding-001"
        model_revision = "001"

        def embed_texts(self, texts, **kwargs):
            nonlocal embedder_called
            embedder_called = True
            return [[0.1] * 384]

    class TrackingGenerator:
        model = "fake"
        provider = "fake"

        async def generate(self, *args, **kwargs):
            nonlocal generator_called
            generator_called = True
            return GenerationResult(answer="A", cited_ids=[], abstained=False, abstention_reason=None)

    counter = MockTokenCounter(error_to_raise=LiveInferenceBlockedError("Live inference dispatch is blocked"))
    retrieval_svc = RetrievalService(embedder=TrackingEmbedder(), token_counter=counter)

    app.dependency_overrides[get_retrieval_service] = lambda: retrieval_svc
    app.dependency_overrides[get_generation_service] = lambda: TrackingGenerator()
    app.dependency_overrides[get_db] = lambda: MockQueryTrackingSession()
    app.dependency_overrides[get_current_actor] = lambda: ActorContext(
        org_id=uuid4(), user_id=uuid4(), effective_roles=["employee"]
    )

    try:
        with TestClient(app) as client:
            resp = client.post("/api/v1/query", json={"question": "What is the policy?"})
            assert resp.status_code == 503
            body = resp.json()
            assert body["code"] == "PROVIDER_UNAVAILABLE"
            assert body["detail"] == "The embedding service is not authorized for live dispatch."
            assert "request_id" in body
            assert UUID(body["request_id"])
            assert resp.headers.get("x-request-id") == body["request_id"]
            assert embedder_called is False
            assert generator_called is False
    finally:
        app.dependency_overrides.clear()


def test_asgi_query_route_zero_leaked_credentials_or_bodies():
    fake_secret = "AIzaSyInternalSecretKey998877"
    counter = MockTokenCounter(error_to_raise=TokenCountingError(f"Failure with {fake_secret}"))
    retrieval_svc = RetrievalService(embedder=None, token_counter=counter)

    app.dependency_overrides[get_retrieval_service] = lambda: retrieval_svc
    app.dependency_overrides[get_db] = lambda: MockQueryTrackingSession()
    app.dependency_overrides[get_current_actor] = lambda: ActorContext(
        org_id=uuid4(), user_id=uuid4(), effective_roles=["employee"]
    )

    try:
        with TestClient(app) as client:
            resp = client.post("/api/v1/query", json={"question": "Test query"})
            text_body = resp.text
            assert fake_secret not in text_body
            assert "traceback" not in text_body.lower()
            assert "AIzaSy" not in text_body
    finally:
        app.dependency_overrides.clear()


def test_google_token_counter_without_ledger_fails_closed_when_dispatch_authorized():
    """F3: When dispatch is authorized, GoogleGenAITokenCounter without a ledger fails closed before HTTP."""
    counter = GoogleGenAITokenCounter(
        api_key="test-key",
        dispatch_policy=MockDispatchPolicy("google"),
        quota_ledger=None,
    )
    with pytest.raises(TokenCountingError, match="A configured QuotaLedger is strictly required"):
        counter.count_tokens("any input text")


@pytest.mark.parametrize("exc_cls", [GeneratorExit, asyncio.CancelledError, KeyboardInterrupt])
def test_google_token_counter_settles_and_reraises_base_exception_unchanged(tmp_path: Path, exc_cls):
    """V5: BaseExceptions (GeneratorExit, CancelledError, KeyboardInterrupt) re-raise unchanged after exactly-once settlement."""
    state_file = tmp_path / f"ledger_base_exc_counter_{exc_cls.__name__}.json"
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=state_file))

    def raise_base_exc(req):
        raise exc_cls("simulated base exception in counter")

    transport = httpx.MockTransport(raise_base_exc)
    counter = GoogleGenAITokenCounter(
        api_key="mock-key-123",
        transport=transport,
        dispatch_policy=MockDispatchPolicy("google"),
        quota_ledger=ledger,
    )

    with pytest.raises(exc_cls) as exc_info:
        counter.count_tokens("sample text to count")

    assert type(exc_info.value) is exc_cls

    with open(state_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data.get("active_reservations", {})) == 0
    settled = data.get("settled_requests", [])
    assert len(settled) == 1
    assert settled[0]["success"] is False
    assert settled[0]["error"] == exc_cls.__name__


def test_token_counter_and_embedder_share_single_model_settings_key(monkeypatch):
    """2a: Token counter and embedder derive their model identity from the single Settings key."""
    from app.services.ingestion.embedding import get_default_embedder

    # Test 1: text-embedding-004 alignment
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "google")
    monkeypatch.setattr(settings, "EMBEDDING_MODEL_NAME", "text-embedding-004")

    embedder = get_default_embedder(provider="google")
    counter = get_default_token_counter()
    assert embedder.model_name == "text-embedding-004"
    assert counter.model_name == "text-embedding-004"
    assert embedder.model_name == counter.model_name

    # Test 2: gemini-embedding-001 alignment
    monkeypatch.setattr(settings, "EMBEDDING_MODEL_NAME", "gemini-embedding-001")
    embedder2 = get_default_embedder(provider="google")
    counter2 = get_default_token_counter()
    assert embedder2.model_name == "gemini-embedding-001"
    assert counter2.model_name == "gemini-embedding-001"
    assert embedder2.model_name == counter2.model_name

    # Test 3: explicit model override alignment
    counter_override = get_default_token_counter(model_name="custom-google-model")
    assert counter_override.model_name == "custom-google-model"
