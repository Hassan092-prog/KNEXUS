import asyncio
import json
import socket
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.api.dependencies import (
    get_db,
    get_dispatch_policy,
    get_embedding_transport,
    get_generation_quota_ledger,
    get_generation_transport,
)
from app.core.config import settings
from app.core.dispatch_policy import (
    BlockedLiveDispatchPolicy,
    LiveInferenceBlockedError,
    ServerApprovedLiveDispatchPolicy,
)
from app.core.generation import GenerationResult
from app.core.quota import QuotaCampaignError, QuotaConfig, QuotaLedger, validate_dispatch_campaign
from app.main import app
from app.services.ingestion.processor import process_document
from tests.phase1.test_hosted_demo_e2e import (
    DEMO_DIR,
    DEMO_DOCX,
    DOCX_MIME,
    EXPECTED_DIRECTION,
    UNRELATED_DIRECTION,
    WATCH_FACT,
    DemoSession,
    _unit_vector,
)


def test_default_is_blocked():
    """Default server state has LIVE_DISPATCH_ENABLED=False and yields BlockedLiveDispatchPolicy."""
    assert settings.LIVE_DISPATCH_ENABLED is False
    policy = get_dispatch_policy()
    assert isinstance(policy, BlockedLiveDispatchPolicy)
    assert policy.can_dispatch is False
    with pytest.raises(LiveInferenceBlockedError):
        policy.check_dispatch("google", settings.EMBEDDING_MODEL_NAME)
    with pytest.raises(LiveInferenceBlockedError):
        policy.check_dispatch("groq", settings.GENERATION_MODEL)


def test_enabled_without_campaign_is_blocked_and_fails_closed(monkeypatch):
    """LIVE_DISPATCH_ENABLED=True with empty/whitespace campaign falls back to BlockedLiveDispatchPolicy."""
    monkeypatch.setattr(settings, "LIVE_DISPATCH_ENABLED", True)
    monkeypatch.setattr(settings, "QUOTA_CAMPAIGN_ID", "")
    policy = get_dispatch_policy()
    assert isinstance(policy, BlockedLiveDispatchPolicy)
    with pytest.raises(LiveInferenceBlockedError):
        policy.check_dispatch("google", settings.EMBEDDING_MODEL_NAME)

    monkeypatch.setattr(settings, "QUOTA_CAMPAIGN_ID", "   ")
    policy_ws = get_dispatch_policy()
    assert isinstance(policy_ws, BlockedLiveDispatchPolicy)

    # ServerApprovedLiveDispatchPolicy without a valid ledger or with default campaign fails closed
    server_policy = ServerApprovedLiveDispatchPolicy()
    assert server_policy.can_dispatch is True
    with pytest.raises(QuotaCampaignError, match="strictly required"):
        validate_dispatch_campaign(server_policy, None)

    cfg = QuotaConfig(enabled=True, campaign_id="default")
    with pytest.raises(QuotaCampaignError, match="refused"):
        validate_dispatch_campaign(server_policy, QuotaLedger(cfg))


def test_enabled_with_campaign_allows_only_exact_pairs(monkeypatch):
    """ServerApprovedLiveDispatchPolicy permits only configured (google, emb) and (groq, gen) pairs."""
    monkeypatch.setattr(settings, "LIVE_DISPATCH_ENABLED", True)
    monkeypatch.setattr(settings, "QUOTA_CAMPAIGN_ID", "phase1-live-demo-20261107")
    monkeypatch.setattr(settings, "EMBEDDING_MODEL_NAME", "gemini-embedding-001")
    monkeypatch.setattr(settings, "GENERATION_MODEL", "openai/gpt-oss-120b")

    policy = get_dispatch_policy()
    assert isinstance(policy, ServerApprovedLiveDispatchPolicy)
    assert policy.can_dispatch is True

    # Exact pairs allowed
    policy.check_dispatch("google", "gemini-embedding-001")
    policy.check_dispatch("groq", "openai/gpt-oss-120b")

    # Wrong provider or wrong model rejected
    with pytest.raises(LiveInferenceBlockedError):
        policy.check_dispatch("google", "text-embedding-004")
    with pytest.raises(LiveInferenceBlockedError):
        policy.check_dispatch("groq", "llama-3.3-70b-versatile")
    with pytest.raises(LiveInferenceBlockedError):
        policy.check_dispatch("openai", "openai/gpt-oss-120b")
    with pytest.raises(LiveInferenceBlockedError):
        policy.check_dispatch("ollama", "llama3.2:3b")


def test_upload_and_query_with_live_flag_hits_mocks_and_records_quota(monkeypatch, tmp_path):
    """With LIVE_DISPATCH_ENABLED=True, real routes hit mock transports and record quota on ledger."""
    def _no_socket(*args, **kwargs):
        raise AssertionError("live dispatch test must not open real sockets")

    monkeypatch.setattr(socket, "create_connection", _no_socket)

    session = DemoSession()
    google_requests: list[httpx.Request] = []
    groq_requests: list[httpx.Request] = []

    async def override_db():
        yield session

    async def no_background_work(*args, **kwargs):
        return True

    from app.api.v1.endpoints import documents as document_routes
    monkeypatch.setattr(document_routes, "process_document", no_background_work)

    campaign_id = "opt-in-live-e2e-20261108"
    monkeypatch.setattr(settings, "LIVE_DISPATCH_ENABLED", True)
    monkeypatch.setattr(settings, "QUOTA_CAMPAIGN_ID", campaign_id)
    monkeypatch.setattr(settings, "DOCUMENT_STORAGE_ROOT", tmp_path / "private")
    monkeypatch.setattr(settings, "QUOTA_STATE_PATH", tmp_path / "quota_state.json")
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "google")
    monkeypatch.setattr(settings, "EMBEDDING_MODEL_NAME", "gemini-embedding-001")
    monkeypatch.setattr(settings, "EMBEDDING_API_KEY", SecretStr("fake-google-key"))
    monkeypatch.setattr(settings, "GENERATION_PROVIDER", "groq")
    monkeypatch.setattr(settings, "GENERATION_MODEL", "openai/gpt-oss-120b")
    monkeypatch.setattr(settings, "GENERATION_API_KEY", SecretStr("fake-groq-key"))

    ledger = QuotaLedger(
        QuotaConfig(
            enabled=True,
            campaign_id=campaign_id,
            max_campaign_attempts=500,
            max_requests_per_minute=1000,
            max_requests_per_day=10000,
            min_request_interval_seconds=0.0,
            state_path=tmp_path / "quota_state.json",
        )
    )
    monkeypatch.setattr("app.core.quota.get_process_quota_ledger", lambda: ledger)

    def google_handler(request: httpx.Request) -> httpx.Response:
        google_requests.append(request)
        payload = json.loads(request.content.decode("utf-8"))
        if ":countTokens" in str(request.url):
            text = payload["contents"][0]["parts"][0]["text"]
            return httpx.Response(200, json={"totalTokens": max(1, len(text) // 4)})
        embeddings = []
        for request_entry in payload["requests"]:
            if request_entry.get("taskType") == "RETRIEVAL_QUERY":
                embeddings.append({"values": _unit_vector(EXPECTED_DIRECTION)})
                continue
            text = request_entry["content"]["parts"][0]["text"]
            direction = EXPECTED_DIRECTION if WATCH_FACT in text else UNRELATED_DIRECTION
            embeddings.append({"values": _unit_vector(direction)})
        return httpx.Response(200, json={"embeddings": embeddings})

    def groq_handler(request: httpx.Request) -> httpx.Response:
        groq_requests.append(request)
        result = GenerationResult(
            answer="According to the policy: " + WATCH_FACT + " [1].",
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
    monkeypatch.setattr("app.api.dependencies.get_embedding_transport", lambda: google_transport)
    monkeypatch.setattr("app.api.dependencies.get_generation_transport", lambda: groq_transport)

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_generation_quota_ledger] = lambda: ledger
    app.dependency_overrides[get_embedding_transport] = lambda: google_transport
    app.dependency_overrides[get_generation_transport] = lambda: groq_transport

    try:
        with TestClient(app) as client:
            # 1. Upload document
            roles = json.loads((DEMO_DIR / "manifest.json").read_text(encoding="utf-8"))["documents"]
            allowed_roles = next(
                entry["allowed_roles"] for entry in roles if entry["filename"] == "demo_security_policy.docx"
            )
            upload_resp = client.post(
                "/api/v1/documents/upload",
                files=[
                    ("file", ("demo_security_policy.docx", DEMO_DOCX.read_bytes(), DOCX_MIME)),
                    *[("allowed_roles", (None, r)) for r in allowed_roles],
                    ("title", (None, "Security Policy")),
                ],
            )
            assert upload_resp.status_code == 202
            doc_id = UUID(upload_resp.json()["document_id"])

            # 2. Process document using default factory (resolves policy, ledger and embedding transport)
            assert asyncio.run(process_document(doc_id, session_factory=lambda: session)) is True
            assert len(google_requests) > 0, "google transport should receive token count and embedding requests"

            # 3. Query document through API
            questions = json.loads((DEMO_DIR / "questions.json").read_text(encoding="utf-8"))["questions"]
            q01 = next(q for q in questions if q["id"] == "demo_q01")
            query_resp = client.post(
                "/api/v1/query",
                json={"question": q01["question"], "top_k": 5, "stream": False},
            )
            assert query_resp.status_code == 200
            body = query_resp.json()
            assert body["abstained"] is False
            assert len(body["citations"]) > 0
            assert len(groq_requests) > 0, "groq transport should receive chat completion request"

            # 4. Quota recording verified
            state = ledger._load_state()
            assert len(state["settled_requests"]) > 0
            settled_campaigns = {r.get("campaign_id") for r in state["settled_requests"]}
            assert campaign_id in settled_campaigns
    finally:
        app.dependency_overrides.clear()
