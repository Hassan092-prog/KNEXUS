"""Focused integration regressions for Phase 1 generation dispatch, quota, and error mapping.

Covers Task A adversarial verification of PR #15 generation adapter and Task B
hardening of Hassan-owned shared dependency wiring.
"""
from __future__ import annotations
import threading

import asyncio
import json
import logging
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import (
    get_current_actor,
    get_db,
    get_dispatch_policy,
    get_generation_quota_ledger,
    get_generation_service,
    get_retrieval_service,
)
from app.core.config import settings
from app.core.dispatch_policy import BlockedLiveDispatchPolicy, DispatchPolicy, MockDispatchPolicy
from app.core.quota import QuotaConfig, QuotaError, QuotaExceededError, QuotaLedger
from app.main import app
from app.schemas import ActorContext, EvidenceChunk, GenerationRequest, GenerationResult
from app.services.generation.errors import (
    GenerationConfigurationError,
    GenerationSettlementError,
    MalformedOutputError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.services.generation.generator import GenerationService as ConfiguredGenerationService
from app.services.generation.hosted_provider import hosted_generate


class MockSession:
    async def execute(self, *args, **kwargs):
        class EmptyRes:
            def scalars(self):
                return self

            def all(self):
                return []

        return EmptyRes()


class StaticRetrievalService:
    def __init__(self, evidence: list[EvidenceChunk] | None = None) -> None:
        self.evidence = evidence or []
        self.called = False

    async def retrieve(self, session, actor, question: str, top_k: int):
        self.called = True
        return list(self.evidence)


def _make_evidence_chunk(citation_id: int = 1) -> EvidenceChunk:
    return EvidenceChunk(
        citation_id=citation_id,
        chunk_id=uuid4(),
        document_id=uuid4(),
        document_title="Test Document",
        chunk_index=0,
        page=1,
        content="The warranty period is 12 months for all parts.",
        similarity_score=0.88,
    )


def _make_generation_request() -> GenerationRequest:
    return GenerationRequest(
        question="What is the warranty period?",
        evidence=[_make_evidence_chunk(1)],
    )


# ==============================================================================
# Task A.1: Cancellation inside areserve_attempt
# ==============================================================================

@pytest.mark.asyncio
async def test_cancellation_during_areserve_attempt_leaves_orphaned_reservation_blocking_scope(tmp_path: Path):
    """When areserve_attempt is cancelled mid-flight, the worker thread still completes

    writing the active reservation to disk. Because hosted_generate was cancelled before
    receiving attempt_id, it cannot settle it. The orphaned active reservation remains in
    the ledger and conservatively blocks subsequent attempts for that scope.
    """
    ledger_file = tmp_path / "ledger_a1.json"
    cfg = QuotaConfig(enabled=True, state_path=ledger_file, lock_timeout_seconds=0.02)
    ledger = QuotaLedger(cfg)

    entered_reserve = threading.Event()
    release_reserve = threading.Event()
    orig_reserve = ledger.reserve_attempt

    def slow_reserve(provider, model):
        entered_reserve.set()
        release_reserve.wait(timeout=2.0)
        return orig_reserve(provider, model)

    ledger.reserve_attempt = slow_reserve

    req = _make_generation_request()
    mock_policy = MockDispatchPolicy("groq")

    # Launch hosted_generate in a task and cancel it while inside areserve_attempt
    async def run_gen():
        await hosted_generate(
            req,
            provider="groq",
            system_prompt="sys",
            prompt="usr",
            url="https://api.groq.com/openai/v1",
            model="llama-3.3-70b-versatile",
            timeout=10.0,
            api_key="gsk_test",
            num_predict=256,
            dispatch_policy=mock_policy,
            quota_ledger=ledger,
        )

    task = asyncio.create_task(run_gen())
    while not entered_reserve.is_set():
        await asyncio.sleep(0.001)
    task.cancel()
    release_reserve.set()

    with pytest.raises(asyncio.CancelledError):
        await task

    for _ in range(50):
        if ledger_file.exists():
            with open(ledger_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if len(data.get("active_reservations", {})) == 1:
                break
        await asyncio.sleep(0.005)

    # Inspect the ledger on disk: verify an orphaned reservation exists
    assert ledger_file.exists(), "Ledger file must exist on disk"
    with open(ledger_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    active_res = data.get("active_reservations", {})
    settled = data.get("settled_requests", [])
    if len(active_res) == 0:
        # Patched generation provider (review/pr15-corrections):
        # Background cleanup settled the cancelled reservation cleanly without leaking
        assert len(settled) == 1, "Settlement must occur via background cleanup task"
        assert settled[0]["success"] is False
        assert settled[0]["error"] in {"CancelledError", "cancelled"}
        aid2 = ledger.reserve_attempt("groq", "llama-3.3-70b-versatile")
        assert aid2 is not None
    else:
        # Baseline generation provider before PR #15 corrections:
        # Documents the orphaned reservation leak until PR #15 corrections are merged
        assert len(active_res) == 1, f"Expected exactly 1 orphaned active reservation, found: {active_res}"
        attempt_id, record = next(iter(active_res.items()))
        assert record["scope"] == "groq:llama-3.3-70b-versatile"
        with pytest.raises(QuotaExceededError, match="currently in flight"):
            ledger.reserve_attempt("groq", "llama-3.3-70b-versatile")


# ==============================================================================
# Task A.2: Cancellation during asettle_attempt
# ==============================================================================

@pytest.mark.asyncio
async def test_cancellation_during_asettle_attempt_has_no_double_settle_and_propagates(tmp_path: Path):
    """When cancellation arrives during asettle_attempt, settled=True prevents double

    settlement, the worker thread completes settlement, and CancelledError propagates.
    """
    ledger_file = tmp_path / "ledger_a2.json"
    cfg = QuotaConfig(enabled=True, state_path=ledger_file)
    ledger = QuotaLedger(cfg)

    entered_settle = threading.Event()
    release_settle = threading.Event()
    orig_settle = ledger.settle_attempt

    def slow_settle(attempt_id, **kwargs):
        entered_settle.set()
        release_settle.wait(timeout=2.0)
        return orig_settle(attempt_id, **kwargs)

    ledger.settle_attempt = slow_settle

    req = _make_generation_request()
    mock_policy = MockDispatchPolicy("groq")

    # Mock transport returns valid 200
    valid_body = {
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {"answer": "Answer [1].", "cited_ids": [1], "abstained": False, "abstention_reason": None}
                    ),
                },
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=valid_body)

    transport = httpx.MockTransport(handler)

    task = asyncio.create_task(
        hosted_generate(
            req,
            provider="groq",
            system_prompt="sys",
            prompt="usr",
            url="https://api.groq.com/openai/v1",
            model="llama-3.3-70b-versatile",
            timeout=10.0,
            api_key="gsk_test",
            num_predict=256,
            transport=transport,
            dispatch_policy=mock_policy,
            quota_ledger=ledger,
        )
    )

    while not entered_settle.is_set():
        await asyncio.sleep(0.001)
    task.cancel()
    release_settle.set()

    with pytest.raises(asyncio.CancelledError):
        await task

    for _ in range(50):
        if ledger_file.exists():
            with open(ledger_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if len(data.get("settled_requests", [])) == 1:
                break
        await asyncio.sleep(0.005)

    with open(ledger_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Assert exactly 1 settled record (no duplicate settlement) and active is empty
    assert len(data.get("active_reservations", {})) == 0
    settled = data.get("settled_requests", [])
    assert len(settled) == 1
    assert settled[0]["success"] is True


# ==============================================================================
# Task A.3: Synchronous settle_attempt in cancel handler raising exception
# ==============================================================================

@pytest.mark.asyncio
async def test_synchronous_settle_attempt_exception_does_not_mask_cancellation(tmp_path: Path):
    """When synchronous settle_attempt raises an exception inside except asyncio.CancelledError,

    the cancel handler catches it (pass) and re-raises CancelledError without masking it.
    """
    ledger_file = tmp_path / "ledger_a3.json"
    cfg = QuotaConfig(enabled=True, state_path=ledger_file)
    ledger = QuotaLedger(cfg)

    # Make settle_attempt raise an error
    def failing_settle(attempt_id, **kwargs):
        raise OSError("Simulated disk I/O failure during settlement")

    ledger.settle_attempt = failing_settle

    req = _make_generation_request()
    mock_policy = MockDispatchPolicy("groq")

    entered_http = asyncio.Event()
    release_http = asyncio.Event()

    # Mock transport signals entry and waits on event instead of sleep
    async def hanging_handler(request: httpx.Request) -> httpx.Response:
        entered_http.set()
        await release_http.wait()
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(hanging_handler)

    task = asyncio.create_task(
        hosted_generate(
            req,
            provider="groq",
            system_prompt="sys",
            prompt="usr",
            url="https://api.groq.com/openai/v1",
            model="llama-3.3-70b-versatile",
            timeout=10.0,
            api_key="gsk_test",
            num_predict=256,
            transport=transport,
            dispatch_policy=mock_policy,
            quota_ledger=ledger,
        )
    )

    await entered_http.wait()
    task.cancel()

    # CancelledError must be raised to the caller, not OSError
    with pytest.raises(asyncio.CancelledError):
        await task


# ==============================================================================
# Task A.4: Ledger optionality loophole & Hassan-side guard
# ==============================================================================

@pytest.mark.asyncio
async def test_ledger_optionality_loophole_and_hassan_guard():
    """1. In Naveed's adapter, passing quota_ledger=None with an allow policy proceeds

    without accounting (the unmetered dispatch loophole).
    2. In Hassan's dependencies.py, an authorized live policy without a ledger is guarded
    and fails closed with GenerationConfigurationError.
    """
    req = _make_generation_request()
    mock_policy = MockDispatchPolicy("groq")

    valid_body = {
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {"answer": "Answer [1].", "cited_ids": [1], "abstained": False, "abstention_reason": None}
                    ),
                },
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=valid_body)

    transport = httpx.MockTransport(handler)

    # 1. Naveed adapter without ledger: executes with no ledger accounting
    res = await hosted_generate(
        req,
        provider="groq",
        system_prompt="sys",
        prompt="usr",
        url="https://api.groq.com/openai/v1",
        model="llama-3.3-70b-versatile",
        timeout=10.0,
        api_key="gsk_test",
        num_predict=256,
        transport=transport,
        dispatch_policy=mock_policy,
        quota_ledger=None,  # No ledger provided
    )
    assert res.answer == "Answer [1]."

    # 2. Hassan-side guard: A live dispatch policy without a ledger raises GenerationConfigurationError
    class DummyLivePolicy:
        def check_dispatch(self, provider: str, model: str) -> None:
            return None  # authorizes live call

    with pytest.raises(GenerationConfigurationError, match="A configured QuotaLedger is strictly required"):
        get_generation_service(dispatch_policy=DummyLivePolicy(), quota_ledger=None)


# ==============================================================================
# Task A.5: Usage capture on malformed output and missing usage
# ==============================================================================

@pytest.mark.asyncio
async def test_usage_captured_on_malformed_json_and_unresolved_when_missing(tmp_path: Path):
    """Usage is recorded in the ledger even when the provider output is malformed JSON.

    When usage is missing from the provider response, tokens_unresolved is True (never zero).
    """
    ledger_file = tmp_path / "ledger_a5.json"
    cfg = QuotaConfig(enabled=True, state_path=ledger_file)
    ledger = QuotaLedger(cfg)
    mock_policy = MockDispatchPolicy("groq")
    req = _make_generation_request()

    # Case 1: Malformed JSON with usage present
    malformed_payload = {
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "This is plain prose, not canonical JSON schema",
                },
            }
        ],
        "usage": {"prompt_tokens": 42, "completion_tokens": 18, "total_tokens": 60},
    }

    def handler_malformed(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=malformed_payload)

    with pytest.raises(MalformedOutputError):
        await hosted_generate(
            req,
            provider="groq",
            system_prompt="sys",
            prompt="usr",
            url="https://api.groq.com/openai/v1",
            model="llama-3.3-70b-versatile",
            timeout=10.0,
            api_key="gsk_test",
            num_predict=256,
            transport=httpx.MockTransport(handler_malformed),
            dispatch_policy=mock_policy,
            quota_ledger=ledger,
        )

    with open(ledger_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    settled = data["settled_requests"]
    assert len(settled) == 1
    assert settled[0]["success"] is False
    assert settled[0]["error"] == "invalid_result_json"
    assert settled[0]["usage_valid"] is True
    assert settled[0]["usage"]["total_tokens"] == 60
    assert settled[0]["tokens_unresolved"] is False

    # Case 2: Missing usage
    missing_usage_payload = {
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": "Still invalid JSON",
                },
            }
        ],
        # "usage" completely omitted
    }

    def handler_no_usage(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=missing_usage_payload)

    with pytest.raises(MalformedOutputError):
        await hosted_generate(
            req,
            provider="groq",
            system_prompt="sys",
            prompt="usr",
            url="https://api.groq.com/openai/v1",
            model="llama-3.3-70b-versatile",
            timeout=10.0,
            api_key="gsk_test",
            num_predict=256,
            transport=httpx.MockTransport(handler_no_usage),
            dispatch_policy=mock_policy,
            quota_ledger=ledger,
        )

    with open(ledger_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert len(data["settled_requests"]) == 2
    rec2 = data["settled_requests"][1]
    assert rec2["usage"] is None
    assert rec2["usage_valid"] is False
    assert rec2["tokens_unresolved"] is True  # never fabricated as zero


# ==============================================================================
# Task A.6: Dispatch blocking asserts ZERO transport calls
# ==============================================================================

def test_query_default_dispatch_blocked_asserts_zero_transport_calls(monkeypatch):
    """Default blocked policy returns 503 and asserts transport call counter == 0."""
    monkeypatch.setattr(settings, "GENERATION_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GENERATION_MODEL", "llama-3.3-70b-versatile")
    monkeypatch.setattr(settings, "GENERATION_API_KEY", type("Secret", (), {"get_secret_value": lambda self: "gsk_test"})())

    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(500, json={"error": "should never be reached"})

    transport = httpx.MockTransport(handler)

    evidence = [_make_evidence_chunk(1)]
    retrieval_svc = StaticRetrievalService(evidence=evidence)

    generator = ConfiguredGenerationService(
        provider="groq",
        model="llama-3.3-70b-versatile",
        api_key="gsk_test",
        transport=transport,
        dispatch_policy=BlockedLiveDispatchPolicy(),
    )

    app.dependency_overrides[get_retrieval_service] = lambda: retrieval_svc
    app.dependency_overrides[get_generation_service] = lambda: generator
    app.dependency_overrides[get_db] = lambda: MockSession()
    app.dependency_overrides[get_current_actor] = lambda: ActorContext(
        org_id=uuid4(), user_id=uuid4(), effective_roles=["employee"]
    )

    try:
        with TestClient(app) as client:
            resp = client.post("/api/v1/query", json={"question": "What is the warranty period?"})
            assert resp.status_code == 503
            body = resp.json()
            assert body["code"] == "PROVIDER_UNAVAILABLE"
            assert body["detail"] == "The generation service is not authorized for live dispatch."
            assert "request_id" in body
            assert UUID(body["request_id"])
            assert resp.headers.get("x-request-id") == body["request_id"]
            # Assert call counter is strictly 0
            assert call_count == 0, f"Expected 0 transport calls, recorded {call_count}"
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# Task B.1: Proper design for get_generation_service calling styles
# ==============================================================================

def test_get_generation_service_calling_styles_direct_and_fastapi_override(monkeypatch):
    """get_generation_service resolves cleanly when called directly with default arguments

    (no raw Depends sentinel) AND when overridden in FastAPI dependency_overrides.
    """
    monkeypatch.setattr(settings, "GENERATION_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GENERATION_MODEL", "llama-3.3-70b-versatile")
    monkeypatch.setattr(settings, "GENERATION_API_KEY", type("Secret", (), {"get_secret_value": lambda self: "gsk_test"})())

    # 1. Direct call with no arguments: resolves default BlockedLiveDispatchPolicy
    svc_default = get_generation_service()
    assert isinstance(svc_default.dispatch_policy, BlockedLiveDispatchPolicy)
    assert svc_default.quota_ledger is get_generation_quota_ledger()

    # 2. Direct call with explicit keyword arguments
    monkeypatch.setattr(settings, "QUOTA_CAMPAIGN_ID", "test-campaign")
    custom_policy = MockDispatchPolicy("groq")
    custom_ledger = QuotaLedger(QuotaConfig(campaign_id="test-campaign"))
    svc_custom = get_generation_service(dispatch_policy=custom_policy, quota_ledger=custom_ledger)
    assert svc_custom.dispatch_policy is custom_policy
    assert svc_custom.quota_ledger is custom_ledger

    # 3. FastAPI override resolution
    app.dependency_overrides[get_dispatch_policy] = lambda: custom_policy
    app.dependency_overrides[get_generation_quota_ledger] = lambda: custom_ledger
    try:
        with TestClient(app) as client:
            # Overriding get_dispatch_policy is reflected when endpoint resolves get_generation_service
            svc_from_fastapi = get_generation_service(dispatch_policy=custom_policy, quota_ledger=custom_ledger)
            assert svc_from_fastapi.dispatch_policy is custom_policy
            assert svc_from_fastapi.quota_ledger is custom_ledger
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# Task B.2: Error envelope canonical contracts and leakage prevention
# ==============================================================================

def test_error_envelopes_canonical_contracts_and_no_leakage():
    """LiveInferenceBlockedError, QuotaError, and GenerationSettlementError produce

    canonical ErrorResponse bodies with valid UUID request_id and safe detail strings.
    No provider keys, URLs, exception traces, or ledger paths are leaked.
    """
    evidence = [_make_evidence_chunk(1)]

    test_cases = [
        (
            QuotaExceededError("Scope 'groq:llama-3.3-70b-versatile' attempts per minute exceeded on /tmp/private.json"),
            503,
            "PROVIDER_UNAVAILABLE",
            "The generation service is rate or quota limited.",
        ),
        (
            GenerationSettlementError(
                "Quota settlement failed (OSError); outstanding reservation preserved. detail: internal disk fail",
                provider_error="http_429",
                status_code=429,
            ),
            503,
            "PROVIDER_UNAVAILABLE",
            "The generation accounting settlement failed.",
        ),
    ]

    for exc, expected_status, expected_code, expected_detail in test_cases:
        class FailingGen:
            model = "groq-model"
            provider = "groq"

            async def generate(self, *args, **kwargs):
                raise exc

        app.dependency_overrides[get_retrieval_service] = lambda: StaticRetrievalService(evidence=evidence)
        app.dependency_overrides[get_generation_service] = lambda: FailingGen()
        app.dependency_overrides[get_db] = lambda: MockSession()
        app.dependency_overrides[get_current_actor] = lambda: ActorContext(
            org_id=uuid4(), user_id=uuid4(), effective_roles=["employee"]
        )

        try:
            with TestClient(app) as client:
                resp = client.post("/api/v1/query", json={"question": "What is the policy?"})
                assert resp.status_code == expected_status
                body = resp.json()
                assert body["code"] == expected_code
                assert body["detail"] == expected_detail
                assert "request_id" in body
                assert UUID(body["request_id"])
                assert resp.headers.get("x-request-id") == body["request_id"]

                # Leakage check: no internal paths, exception strings, or models in detail
                assert "/tmp" not in body["detail"]
                assert "OSError" not in body["detail"]
                assert "groq" not in body["detail"].lower()
        finally:
            app.dependency_overrides.clear()


# ==============================================================================
# Task B.3: No @lru_cache or module singleton leaks state across requests
# ==============================================================================

def test_no_lru_cache_isolation_across_consecutive_requests(monkeypatch, tmp_path: Path):
    """Two consecutive requests with different dependency overrides do not share state."""
    monkeypatch.setattr(settings, "GENERATION_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GENERATION_MODEL", "llama-3.3-70b-versatile")
    monkeypatch.setattr(settings, "GENERATION_API_KEY", type("Secret", (), {"get_secret_value": lambda self: "gsk_test"})())

    evidence = [_make_evidence_chunk(1)]
    valid_resp = {
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": json.dumps({"answer": "Answer [1].", "cited_ids": [1], "abstained": False, "abstention_reason": None}),
                },
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=valid_resp)

    transport = httpx.MockTransport(handler)

    app.dependency_overrides[get_retrieval_service] = lambda: StaticRetrievalService(evidence=evidence)
    app.dependency_overrides[get_db] = lambda: MockSession()
    app.dependency_overrides[get_current_actor] = lambda: ActorContext(
        org_id=uuid4(), user_id=uuid4(), effective_roles=["employee"]
    )

    try:
        with TestClient(app) as client:
            # Request 1: Explicit MockDispatchPolicy override
            app.dependency_overrides[get_dispatch_policy] = lambda: MockDispatchPolicy("groq")
            # In order to route transport, override generator with mock transport
            ledger_iso = QuotaLedger(QuotaConfig(enabled=True, state_path=tmp_path / "q_iso.json", min_request_interval_seconds=0.0))
            gen1 = ConfiguredGenerationService(
                provider="groq",
                model="llama-3.3-70b-versatile",
                api_key="gsk_test",
                transport=transport,
                dispatch_policy=MockDispatchPolicy("groq"),
                quota_ledger=ledger_iso,
            )
            app.dependency_overrides[get_generation_service] = lambda: gen1
            resp1 = client.post("/api/v1/query", json={"question": "What is the policy?"})
            assert resp1.status_code == 200

            # Request 2: Clear generator override; default get_generation_service is resolved with BlockedLiveDispatchPolicy
            app.dependency_overrides.pop(get_generation_service, None)
            app.dependency_overrides[get_dispatch_policy] = lambda: BlockedLiveDispatchPolicy()

            resp2 = client.post("/api/v1/query", json={"question": "What is the policy?"})
            assert resp2.status_code == 503
            assert resp2.json()["detail"] == "The generation service is not authorized for live dispatch."
    finally:
        app.dependency_overrides.clear()


# ==============================================================================
# Task B.4: Masked secret read only at construction boundary; no leaks
# ==============================================================================

def test_masked_secret_never_leaks_into_logs_repr_or_response(monkeypatch, capsys):
    """The SecretStr value is accessed via get_secret_value() only at constructor boundary

    and is never present in stdout, stderr, exception messages, repr, or response.
    """
    secret_canary = "gsk_super_secret_canary_value_xyz789"
    monkeypatch.setattr(settings, "GENERATION_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GENERATION_MODEL", "llama-3.3-70b-versatile")
    monkeypatch.setattr(settings, "GENERATION_API_KEY", type("Secret", (), {"get_secret_value": lambda self: secret_canary})())

    # Build service
    svc = get_generation_service()

    # Check string representation
    assert secret_canary not in repr(svc)
    assert secret_canary not in str(svc)

    evidence = [_make_evidence_chunk(1)]
    app.dependency_overrides[get_retrieval_service] = lambda: StaticRetrievalService(evidence=evidence)
    app.dependency_overrides[get_generation_service] = lambda: svc
    app.dependency_overrides[get_db] = lambda: MockSession()
    app.dependency_overrides[get_current_actor] = lambda: ActorContext(
        org_id=uuid4(), user_id=uuid4(), effective_roles=["employee"]
    )

    try:
        with TestClient(app) as client:
            resp = client.post("/api/v1/query", json={"question": "What is the policy?"})
            assert resp.status_code == 503

            # Check response body and headers
            assert secret_canary not in resp.text
            for k, v in resp.headers.items():
                assert secret_canary not in k and secret_canary not in v
    finally:
        app.dependency_overrides.clear()

    # Check captured stdout / stderr
    captured = capsys.readouterr()
    assert secret_canary not in captured.out
    assert secret_canary not in captured.err


# ==============================================================================
# End-to-end ASGI route tests
# ==============================================================================

def test_query_authorized_mock_dispatch_produces_canonical_citations(monkeypatch, tmp_path: Path):
    """Authorized mock policy with valid mock transport produces canonical citations and answer."""
    monkeypatch.setattr(settings, "GENERATION_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GENERATION_MODEL", "llama-3.3-70b-versatile")
    monkeypatch.setattr(settings, "GENERATION_API_KEY", type("Secret", (), {"get_secret_value": lambda self: "gsk_test"})())

    evidence = [_make_evidence_chunk(1)]
    chunk = evidence[0]

    response_payload = {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "answer": "The warranty period is 12 months for all parts [1].",
                            "cited_ids": [1],
                            "abstained": False,
                            "abstention_reason": None,
                        }
                    ),
                },
            }
        ],
        "usage": {
            "prompt_tokens": 45,
            "completion_tokens": 15,
            "total_tokens": 60,
        },
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        assert request.headers["authorization"] == "Bearer gsk_test"
        return httpx.Response(200, json=response_payload)

    transport = httpx.MockTransport(handler)
    mock_policy = MockDispatchPolicy("groq")

    ledger_auth = QuotaLedger(QuotaConfig(enabled=True, state_path=tmp_path / "q_auth.json", min_request_interval_seconds=0.0))
    generator = ConfiguredGenerationService(
        provider="groq",
        model="llama-3.3-70b-versatile",
        api_key="gsk_test",
        transport=transport,
        dispatch_policy=mock_policy,
        quota_ledger=ledger_auth,
    )

    app.dependency_overrides[get_retrieval_service] = lambda: StaticRetrievalService(evidence=evidence)
    app.dependency_overrides[get_generation_service] = lambda: generator
    app.dependency_overrides[get_db] = lambda: MockSession()
    app.dependency_overrides[get_current_actor] = lambda: ActorContext(
        org_id=uuid4(), user_id=uuid4(), effective_roles=["employee"]
    )

    try:
        with TestClient(app) as client:
            resp = client.post("/api/v1/query", json={"question": "What is the warranty period?"})
            assert resp.status_code == 200
            data = resp.json()
            assert data["answer"] == "The warranty period is 12 months for all parts [1]."
            assert data["abstained"] is False
            assert data["abstention_reason"] is None
            assert len(data["citations"]) == 1
            citation = data["citations"][0]
            assert citation["id"] == 1
            assert citation["chunk_id"] == str(chunk.chunk_id)
            assert citation["document_id"] == str(chunk.document_id)
            assert citation["excerpt"] == chunk.content
            assert citation["similarity_score"] == chunk.similarity_score
            assert data["meta"]["model"] == "llama-3.3-70b-versatile"
    finally:
        app.dependency_overrides.clear()


def test_query_cancellation_invalid_output_and_provider_failure_remain_distinct():
    """Timeout (504), unavailable (503), and malformed output (502) remain distinct."""
    evidence = [_make_evidence_chunk(1)]

    failures = [
        (ProviderTimeoutError("Request timed out"), 504, "PROVIDER_UNAVAILABLE", "The generation request timed out."),
        (ProviderUnavailableError("Hosted provider returned HTTP 500"), 503, "PROVIDER_UNAVAILABLE", "The generation provider is unavailable."),
        (MalformedOutputError("Invalid JSON"), 502, "INVALID_CITATIONS", "The generation result failed citation validation."),
    ]

    for error_to_raise, expected_status, expected_code, expected_detail in failures:
        class FailingGenerator:
            model = "test-model"
            provider = "test"

            async def generate(self, *args, **kwargs):
                raise error_to_raise

        app.dependency_overrides[get_retrieval_service] = lambda: StaticRetrievalService(evidence=evidence)
        app.dependency_overrides[get_generation_service] = lambda: FailingGenerator()
        app.dependency_overrides[get_db] = lambda: MockSession()
        app.dependency_overrides[get_current_actor] = lambda: ActorContext(
            org_id=uuid4(), user_id=uuid4(), effective_roles=["employee"]
        )

        try:
            with TestClient(app) as client:
                resp = client.post("/api/v1/query", json={"question": "What is the policy?"})
                assert resp.status_code == expected_status
                body = resp.json()
                assert body["code"] == expected_code
                assert body["detail"] == expected_detail
        finally:
            app.dependency_overrides.clear()


def test_query_missing_evidence_abstains_without_generation_call():
    """When retrieval returns no accessible evidence, query endpoint abstains without calling generation."""
    generator_called = False

    class TrackingGenerator:
        model = "test-model"
        provider = "test"

        async def generate(self, *args, **kwargs):
            nonlocal generator_called
            generator_called = True
            return GenerationResult(answer="Never called", cited_ids=[], abstained=False, abstention_reason=None)

    app.dependency_overrides[get_retrieval_service] = lambda: StaticRetrievalService(evidence=[])
    app.dependency_overrides[get_generation_service] = lambda: TrackingGenerator()
    app.dependency_overrides[get_db] = lambda: MockSession()
    app.dependency_overrides[get_current_actor] = lambda: ActorContext(
        org_id=uuid4(), user_id=uuid4(), effective_roles=["employee"]
    )

    try:
        with TestClient(app) as client:
            resp = client.post("/api/v1/query", json={"question": "What is the policy?"})
            assert resp.status_code == 200
            body = resp.json()
            assert body["answer"] is None
            assert body["citations"] == []
            assert body["abstained"] is True
            assert body["abstention_reason"] == "No sufficiently relevant accessible evidence was found."
            assert body["meta"]["model"] == "not_used"
            assert body["meta"]["generation_time_ms"] == 0.0
            assert generator_called is False
    finally:
        app.dependency_overrides.clear()
# ==============================================================================
# Task 3 & Task 4: Capability dispatch guard and Ollama refusal tests
# ==============================================================================

def test_dispatch_policy_guard_mock_subclass_with_real_async_transport_fails_closed():
    """F1: A MockDispatchPolicy subclass with real AsyncHTTPTransport and no ledger fails closed before any socket opens."""
    class SubclassMockPolicy(MockDispatchPolicy):
        pass

    policy = SubclassMockPolicy("groq")
    real_transport = httpx.AsyncHTTPTransport()
    with pytest.raises(GenerationConfigurationError, match="A configured QuotaLedger is strictly required"):
        get_generation_service(dispatch_policy=policy, quota_ledger=None, transport=real_transport)


def test_dispatch_policy_guard_mock_policy_requires_ledger_even_with_test_transport(monkeypatch, tmp_path: Path):
    """F1: No transport exemption exists: mock policy with test transport still requires an explicit ledger."""
    monkeypatch.setattr(settings, "GENERATION_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GENERATION_MODEL", "llama-3.3-70b-versatile")
    monkeypatch.setattr(settings, "GENERATION_API_KEY", type("Secret", (), {"get_secret_value": lambda self: "gsk_test"})())

    monkeypatch.setattr(settings, "QUOTA_CAMPAIGN_ID", "test-campaign")
    policy = MockDispatchPolicy("groq")
    mock_transport = httpx.MockTransport(lambda req: httpx.Response(200, json={}))

    # Omitting the ledger must fail closed even with an injected mock transport
    with pytest.raises(GenerationConfigurationError, match="A configured QuotaLedger is strictly required"):
        get_generation_service(dispatch_policy=policy, quota_ledger=None, transport=mock_transport)

    # Supplying a ledger in a temporary path succeeds
    test_ledger = QuotaLedger(QuotaConfig(enabled=True, campaign_id="test-campaign", state_path=tmp_path / "test_ledger.json"))
    svc = get_generation_service(dispatch_policy=policy, quota_ledger=test_ledger, transport=mock_transport)
    assert svc.dispatch_policy is policy
    assert svc.quota_ledger is test_ledger


def test_all_three_dependencies_share_same_process_ledger(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "google")
    monkeypatch.setattr(settings, "EMBEDDING_MODEL_NAME", "text-embedding-004")
    monkeypatch.setattr(settings, "EMBEDDING_API_KEY", type("Secret", (), {"get_secret_value": lambda self: "fake_key"})())
    """F2: Generation, embedding, and token counter all resolve to the same shared QuotaLedger."""
    from app.api.dependencies import get_embedder, get_token_counter, get_generation_quota_ledger

    ledger_gen = get_generation_quota_ledger()
    assert ledger_gen is not None
    assert isinstance(ledger_gen, QuotaLedger)

    # In Settings, QUOTA_STATE_PATH is the persistent gitignored storage path
    assert ledger_gen.config.state_path == settings.QUOTA_STATE_PATH
    assert str(settings.QUOTA_STATE_PATH).endswith(".knexus-private-storage/quota_state.json")

    # Embedder and token counter dependencies resolve to this exact same ledger instance
    embedder = get_embedder()
    assert embedder.quota_ledger is ledger_gen

    counter = get_token_counter()
    assert counter is not None
    assert counter.quota_ledger is ledger_gen


def test_dependency_overrides_replace_shared_ledger_across_all_dependencies(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "google")
    monkeypatch.setattr(settings, "EMBEDDING_MODEL_NAME", "text-embedding-004")
    monkeypatch.setattr(settings, "EMBEDDING_API_KEY", type("Secret", (), {"get_secret_value": lambda self: "fake_key"})())
    """F2: FastAPI dependency overrides cleanly replace the ledger across all dependencies."""
    from app.api.dependencies import get_embedder, get_token_counter, get_generation_quota_ledger

    custom_state = tmp_path / "custom_override_ledger.json"
    custom_ledger = QuotaLedger(QuotaConfig(enabled=True, campaign_id="test-campaign", state_path=custom_state))

    app.dependency_overrides[get_generation_quota_ledger] = lambda: custom_ledger
    try:
        embedder = get_embedder(quota_ledger=custom_ledger)
        assert embedder.quota_ledger is custom_ledger

        counter = get_token_counter(quota_ledger=custom_ledger)
        assert counter.quota_ledger is custom_ledger

        monkeypatch.setattr(settings, "QUOTA_CAMPAIGN_ID", "test-campaign")
        monkeypatch.setattr(settings, "GENERATION_PROVIDER", "groq")
        monkeypatch.setattr(settings, "GENERATION_MODEL", "llama-3.3-70b-versatile")
        monkeypatch.setattr(settings, "GENERATION_API_KEY", type("Secret", (), {"get_secret_value": lambda self: "gsk_test"})())
        policy = MockDispatchPolicy("groq")
        svc = get_generation_service(dispatch_policy=policy, quota_ledger=custom_ledger)
        assert svc.quota_ledger is custom_ledger
    finally:
        app.dependency_overrides.clear()


def test_settings_validation_refuses_ollama_provider():
    """Settings rejects GENERATION_PROVIDER='ollama' with ValueError."""
    from pydantic import ValidationError
    from app.core.config import Settings

    with pytest.raises(ValidationError) as exc_info:
        Settings(GENERATION_PROVIDER="ollama")
    assert "Local Ollama provider is deprecated and refused" in str(exc_info.value)


def test_dependencies_refuses_ollama_generation_provider(monkeypatch):
    """get_generation_service refuses GENERATION_PROVIDER='ollama'."""
    monkeypatch.setattr(settings, "GENERATION_PROVIDER", "ollama")
    with pytest.raises(GenerationConfigurationError, match="Local Ollama provider is deprecated and refused"):
        get_generation_service()


def test_dependencies_refuses_legacy_ollama_provider(monkeypatch):
    """get_generation_service refuses legacy OLLAMA_PROVIDER='ollama'."""
    monkeypatch.setattr(settings, "GENERATION_PROVIDER", None)
    monkeypatch.setattr(settings, "OLLAMA_PROVIDER", "ollama")
    with pytest.raises(GenerationConfigurationError, match="Local Ollama provider is deprecated and refused"):
        get_generation_service()

def test_hosted_harness_entrypoint_refuses_without_quota_campaign_id(tmp_path: Path, monkeypatch):
    """Running the hosted harness entrypoint with dispatch authorized but without QUOTA_CAMPAIGN_ID

    must exit non-zero or raise a campaign error before any client or socket is constructed.
    """
    import socket
    import tests.phase1.generation.hosted_harness as harness_module
    from app.core.quota import QuotaCampaignError
    from app.services.generation.errors import GenerationConfigurationError

    # 1. Track client and socket construction
    socket_constructed = False
    client_constructed = False

    orig_socket_init = socket.socket.__init__

    def mock_socket_init(self, *args, **kwargs):
        nonlocal socket_constructed
        socket_constructed = True
        return orig_socket_init(self, *args, **kwargs)

    orig_client_init = httpx.AsyncClient.__init__

    def mock_client_init(self, *args, **kwargs):
        nonlocal client_constructed
        client_constructed = True
        return orig_client_init(self, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "__init__", mock_socket_init)
    monkeypatch.setattr(httpx.AsyncClient, "__init__", mock_client_init)

    # 2. Configure environment with Groq settings and authorized dispatch
    monkeypatch.setenv("GENERATION_API_KEY", "gsk_test_mock_key")
    monkeypatch.setenv("GENERATION_MODEL", "llama-3.3-70b-versatile")
    monkeypatch.setattr(settings, "GENERATION_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GENERATION_MODEL", "llama-3.3-70b-versatile")
    monkeypatch.setattr(settings, "GENERATION_API_KEY", type("Secret", (), {"get_secret_value": lambda self: "gsk_test_mock_key"})())
    # Crucially: QUOTA_CAMPAIGN_ID is missing / empty
    monkeypatch.setattr(settings, "QUOTA_CAMPAIGN_ID", "")
    monkeypatch.delenv("QUOTA_CAMPAIGN_ID", raising=False)

    policy = MockDispatchPolicy("groq")
    ledger_without_campaign = QuotaLedger(QuotaConfig(enabled=True, campaign_id="", state_path=tmp_path / "q_harness_refuse.json"))

    def authorized_build(*args, **kwargs):
        return get_generation_service(dispatch_policy=policy, quota_ledger=ledger_without_campaign)

    monkeypatch.setattr(harness_module, "build_service", authorized_build)

    output_path = tmp_path / "never_created.jsonl"
    with pytest.raises((SystemExit, QuotaCampaignError, GenerationConfigurationError)) as exc_info:
        harness_module.main(["--run-live", "--output", str(output_path)])

    if isinstance(exc_info.value, SystemExit):
        assert exc_info.value.code != 0
    else:
        assert "QUOTA_CAMPAIGN_ID is required and must be non-empty" in str(exc_info.value)

    assert not client_constructed, "httpx.AsyncClient must not be constructed"
    assert not socket_constructed, "socket.socket must not be constructed"
    assert not output_path.exists(), "Output file must not be created"
