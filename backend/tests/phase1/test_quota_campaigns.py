"""Offline unit and integration tests for campaign-scoped quota budgets."""
from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from app.api.dependencies import get_generation_service
from app.core.token_counter import GoogleGenAITokenCounter, get_default_token_counter
from app.services.ingestion.embedding import GoogleGenAIEmbedder, get_default_embedder
from app.services.ingestion.errors import EmbeddingUnavailableError, TokenCountingError
from app.core.config import Settings, settings
from app.core.dispatch_policy import MockDispatchPolicy
from app.core.quota import QuotaCampaignError, QuotaConfig, QuotaExceededError, QuotaLedger, validate_dispatch_campaign
from app.services.generation.errors import GenerationConfigurationError


def test_campaign_cap_trips_at_exactly_n(tmp_path: Path):
    """The campaign cap trips at exactly N total attempts for that (campaign_id, scope)."""
    state_file = tmp_path / "campaign_n.json"
    n = 5
    config = QuotaConfig(
        enabled=True,
        campaign_id="camp-alpha",
        max_campaign_attempts=n,
        max_requests_per_minute=100,
        max_requests_per_day=100,
        min_request_interval_seconds=0.0,
        state_path=state_file,
    )
    ledger = QuotaLedger(config)

    for i in range(n):
        aid = ledger.reserve_attempt("google", "gemini-embedding-001")
        assert aid is not None
        ledger.settle_attempt(aid, success=True)

    # Attempt N + 1 must fail with QuotaExceededError
    with pytest.raises(QuotaExceededError) as exc_info:
        ledger.reserve_attempt("google", "gemini-embedding-001")
    assert "attempt limit (5/5) reached" in str(exc_info.value)
    assert "camp-alpha" in str(exc_info.value)


def test_new_campaign_proceeds_while_day_and_minute_caps_still_apply(tmp_path: Path):
    """A new campaign proceeds while global minute and day limits still apply across campaigns."""
    state_file = tmp_path / "multi_campaign.json"

    # Campaign 1: exhaust its budget of 3 attempts
    cfg1 = QuotaConfig(
        enabled=True,
        campaign_id="camp-1",
        max_campaign_attempts=3,
        max_requests_per_minute=10,
        max_requests_per_day=10,
        min_request_interval_seconds=0.0,
        state_path=state_file,
    )
    ledger1 = QuotaLedger(cfg1)
    for _ in range(3):
        aid = ledger1.reserve_attempt("groq", "llama-3.3-70b-versatile")
        ledger1.settle_attempt(aid, success=True)

    # Campaign 1 is now exhausted
    with pytest.raises(QuotaExceededError, match="camp-1"):
        ledger1.reserve_attempt("groq", "llama-3.3-70b-versatile")

    # Campaign 2: starts fresh on the same scope and state file
    cfg2 = QuotaConfig(
        enabled=True,
        campaign_id="camp-2",
        max_campaign_attempts=5,
        max_requests_per_minute=10,
        max_requests_per_day=10,
        min_request_interval_seconds=0.0,
        state_path=state_file,
    )
    ledger2 = QuotaLedger(cfg2)
    # Campaign 2 proceeds
    aid2 = ledger2.reserve_attempt("groq", "llama-3.3-70b-versatile")
    assert aid2 is not None
    ledger2.settle_attempt(aid2, success=True)

    # Now verify that global daily / minute cap still applies across campaigns!
    # Global limit was 10. We have 3 (camp-1) + 1 (camp-2) = 4 attempts.
    # If minute limit is set to 4, next attempt on ANY campaign must fail:
    cfg3 = QuotaConfig(
        enabled=True,
        campaign_id="camp-3",
        max_campaign_attempts=10,
        max_requests_per_minute=4,  # Exactly 4 allowed per minute
        max_requests_per_day=10,
        min_request_interval_seconds=0.0,
        state_path=state_file,
    )
    ledger3 = QuotaLedger(cfg3)
    with pytest.raises(QuotaExceededError, match="requests per minute quota exceeded"):
        ledger3.reserve_attempt("groq", "llama-3.3-70b-versatile")


def test_legacy_state_loads_and_migrates_on_read(tmp_path: Path):
    """An attempt from old format without campaign_id migrates on read as 'legacy'."""
    state_file = tmp_path / "legacy_ledger.json"

    # Pre-populate state file with legacy format (no campaign_id in records)
    legacy_data = {
        "version": 1,
        "created_at": 1000.0,
        "scopes": {
            "google:gemini-embedding-001": {
                "total_attempts": 2,
                "rate_limited": False,
                "rate_limit_reason": None,
                "last_dispatch_time": 1000.0,
            }
        },
        "active_reservations": {
            "legacy-active-1": {
                "reserved_at": 1000.0,
                "provider": "google",
                "model": "gemini-embedding-001",
                "scope": "google:gemini-embedding-001",
                # Note: NO campaign_id here
            }
        },
        "settled_requests": [
            {
                "attempt_id": "legacy-settled-1",
                "scope": "google:gemini-embedding-001",
                "provider": "google",
                "model": "gemini-embedding-001",
                "reserved_at": 900.0,
                "timestamp": 901.0,
                "success": True,
                "error": None,
                "status_code": 200,
                "usage": None,
                "usage_valid": False,
                "tokens_unresolved": True,
                # Note: NO campaign_id here
            }
        ],
    }
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(legacy_data, f)

    # Load with QuotaLedger
    cfg = QuotaConfig(
        enabled=True,
        campaign_id="camp-modern",
        max_campaign_attempts=10,
        state_path=state_file,
        min_request_interval_seconds=0.0,
    )
    ledger = QuotaLedger(cfg)
    loaded = ledger._load_state()

    # In-memory migration assigned "legacy"
    assert loaded["active_reservations"]["legacy-active-1"]["campaign_id"] == "legacy"
    assert loaded["settled_requests"][0]["campaign_id"] == "legacy"

    # Modern campaign has 0 attempts used, so it proceeds freely
    aid = ledger.reserve_attempt("google", "gemini-embedding-001")
    assert aid is not None
    ledger.settle_attempt(aid, success=True)


def test_file_bytes_of_old_records_are_preserved(tmp_path: Path):
    """Saving new records never erases, corrupts, or strips historical campaign records."""
    state_file = tmp_path / "audit_preservation.json"

    # Run Campaign 1
    cfg1 = QuotaConfig(
        enabled=True,
        campaign_id="audit-camp-1",
        max_campaign_attempts=5,
        min_request_interval_seconds=0.0,
        state_path=state_file,
    )
    l1 = QuotaLedger(cfg1)
    a1 = l1.reserve_attempt("groq", "llama-3.3-70b-versatile")
    l1.settle_attempt(a1, success=True)

    # Run Campaign 2
    cfg2 = QuotaConfig(
        enabled=True,
        campaign_id="audit-camp-2",
        max_campaign_attempts=5,
        min_request_interval_seconds=0.0,
        state_path=state_file,
    )
    l2 = QuotaLedger(cfg2)
    a2 = l2.reserve_attempt("groq", "llama-3.3-70b-versatile")
    l2.settle_attempt(a2, success=False, error="provider_error")

    # Read the state file directly from disk
    with open(state_file, "r", encoding="utf-8") as f:
        disk_data = json.load(f)

    settled = disk_data["settled_requests"]
    assert len(settled) == 2
    rec1 = next(r for r in settled if r["attempt_id"] == a1)
    rec2 = next(r for r in settled if r["attempt_id"] == a2)

    assert rec1["campaign_id"] == "audit-camp-1"
    assert rec1["success"] is True
    assert rec2["campaign_id"] == "audit-camp-2"
    assert rec2["success"] is False
    assert rec2["error"] == "provider_error"


def test_generation_fails_closed_without_explicit_campaign_id_or_on_default(monkeypatch, tmp_path: Path):
    """Whenever provider dispatch is authorized, missing, whitespace, 'default' or None ledger fails closed."""
    policy = MockDispatchPolicy("groq")
    mock_transport = httpx.MockTransport(lambda req: httpx.Response(200, json={}))
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=tmp_path / "q_disp.json"))

    # 1. Empty string fails closed
    monkeypatch.setattr(settings, "QUOTA_CAMPAIGN_ID", "")
    with pytest.raises(GenerationConfigurationError, match="QUOTA_CAMPAIGN_ID is required and must be non-empty"):
        get_generation_service(dispatch_policy=policy, quota_ledger=ledger, transport=mock_transport)

    # 2. Whitespace-only string fails closed
    monkeypatch.setattr(settings, "QUOTA_CAMPAIGN_ID", "   ")
    with pytest.raises(GenerationConfigurationError, match="QUOTA_CAMPAIGN_ID is required and must be non-empty"):
        get_generation_service(dispatch_policy=policy, quota_ledger=ledger, transport=mock_transport)

    # 3. Campaign 'default' is explicitly refused (no silent fallback permitted)
    monkeypatch.setattr(settings, "QUOTA_CAMPAIGN_ID", "default")
    with pytest.raises(GenerationConfigurationError, match="Silent fallback to campaign 'default' is refused"):
        get_generation_service(dispatch_policy=policy, quota_ledger=ledger, transport=mock_transport)

    # 4. QuotaLedger is None fails closed
    monkeypatch.setattr(settings, "QUOTA_CAMPAIGN_ID", "campaign-valid-123")
    with pytest.raises(GenerationConfigurationError, match="A configured QuotaLedger is strictly required"):
        get_generation_service(dispatch_policy=policy, quota_ledger=None, transport=mock_transport)

    # 5. Non-empty, non-default string succeeds
    monkeypatch.setattr(settings, "QUOTA_CAMPAIGN_ID", "campaign-valid-123")
    svc = get_generation_service(dispatch_policy=policy, quota_ledger=ledger, transport=mock_transport)
    assert svc is not None


def test_expired_unresolved_and_unresolved_token_attempts_count_toward_campaign(tmp_path: Path):
    """Expired-unresolved and unresolved-token attempts count fully toward the campaign budget."""
    state_file = tmp_path / "unresolved_campaign.json"
    cfg = QuotaConfig(
        enabled=True,
        campaign_id="camp-unresolved",
        max_campaign_attempts=2,
        min_request_interval_seconds=0.0,
        in_flight_timeout_seconds=0.01,
        state_path=state_file,
    )
    ledger = QuotaLedger(cfg)

    # Attempt 1: settled with unresolved tokens
    aid1 = ledger.reserve_attempt("google", "gemini-embedding-001")
    ledger.settle_attempt(aid1, success=True, usage={"prompt_tokens": 10})  # missing completion/total -> tokens_unresolved=True

    # Attempt 2: allowed to expire (expired_unresolved)
    aid2 = ledger.reserve_attempt("google", "gemini-embedding-001")
    import time
    time.sleep(0.02)  # exceed in_flight_timeout_seconds

    # Next attempt triggers stale recovery of aid2 into expired_unresolved
    # Since aid1 (unresolved token) and aid2 (expired_unresolved) both count toward the cap of 2,
    # attempt 3 must be refused!
    with pytest.raises(QuotaExceededError, match=r"attempt limit \(2/2\) reached"):
        ledger.reserve_attempt("google", "gemini-embedding-001")


def test_embedder_fails_closed_without_explicit_campaign_id_or_on_default(monkeypatch, tmp_path: Path):
    """GoogleGenAIEmbedder and get_default_embedder fail closed when dispatch is authorized but campaign ID is missing or 'default'."""
    policy = MockDispatchPolicy("google")
    monkeypatch.setattr(settings, "QUOTA_CAMPAIGN_ID", "")
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "google")
    monkeypatch.setattr(settings, "EMBEDDING_MODEL_NAME", "text-embedding-004")

    # 1. Missing campaign ID fails closed
    ledger_default = QuotaLedger(QuotaConfig(enabled=True, campaign_id="default", state_path=tmp_path / "q_emb_def.json"))
    with pytest.raises(EmbeddingUnavailableError, match="QUOTA_CAMPAIGN_ID is required and must be non-empty"):
        GoogleGenAIEmbedder(
            api_key="test-key",
            dispatch_policy=policy,
            quota_ledger=ledger_default,
        )

    # 2. Explicit 'default' campaign fails closed
    monkeypatch.setattr(settings, "QUOTA_CAMPAIGN_ID", "default")
    with pytest.raises(EmbeddingUnavailableError, match="Silent fallback to campaign 'default' is refused"):
        GoogleGenAIEmbedder(
            api_key="test-key",
            dispatch_policy=policy,
            quota_ledger=ledger_default,
        )

    # 3. get_default_embedder fails closed with default campaign
    with pytest.raises(EmbeddingUnavailableError, match="Silent fallback to campaign 'default' is refused"):
        get_default_embedder(provider="google", dispatch_policy=policy, quota_ledger=ledger_default)

    # 3. Missing ledger fails closed
    with pytest.raises(EmbeddingUnavailableError, match="A configured QuotaLedger is strictly required"):
        GoogleGenAIEmbedder(
            api_key="test-key",
            dispatch_policy=policy,
            quota_ledger=None,
        )

    # 4. Valid non-default campaign succeeds
    ledger_valid = QuotaLedger(QuotaConfig(enabled=True, campaign_id="valid-embed-campaign", state_path=tmp_path / "q_emb_val.json"))
    embedder = GoogleGenAIEmbedder(
        api_key="test-key",
        dispatch_policy=policy,
        quota_ledger=ledger_valid,
    )
    assert embedder is not None


def test_token_counter_fails_closed_without_explicit_campaign_id_or_on_default(monkeypatch, tmp_path: Path):
    """GoogleGenAITokenCounter and get_default_token_counter fail closed when dispatch is authorized but campaign ID is missing or 'default'."""
    policy = MockDispatchPolicy("google")
    monkeypatch.setattr(settings, "QUOTA_CAMPAIGN_ID", "")
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "google")
    monkeypatch.setattr(settings, "EMBEDDING_MODEL_NAME", "text-embedding-004")

    # 1. Missing campaign ID fails closed
    ledger_default = QuotaLedger(QuotaConfig(enabled=True, campaign_id="default", state_path=tmp_path / "q_cnt_def.json"))
    with pytest.raises(TokenCountingError, match="QUOTA_CAMPAIGN_ID is required and must be non-empty"):
        GoogleGenAITokenCounter(
            api_key="test-key",
            dispatch_policy=policy,
            quota_ledger=ledger_default,
        )

    # 2. Explicit 'default' campaign fails closed
    monkeypatch.setattr(settings, "QUOTA_CAMPAIGN_ID", "default")
    with pytest.raises(TokenCountingError, match="Silent fallback to campaign 'default' is refused"):
        GoogleGenAITokenCounter(
            api_key="test-key",
            dispatch_policy=policy,
            quota_ledger=ledger_default,
        )

    # 3. get_default_token_counter fails closed with default campaign
    with pytest.raises(TokenCountingError, match="Silent fallback to campaign 'default' is refused"):
        get_default_token_counter(dispatch_policy=policy, quota_ledger=ledger_default)

    # 3. Missing ledger fails closed
    with pytest.raises(TokenCountingError, match="A configured QuotaLedger is strictly required"):
        GoogleGenAITokenCounter(
            api_key="test-key",
            dispatch_policy=policy,
            quota_ledger=None,
        )

    # 4. Valid non-default campaign succeeds
    ledger_valid = QuotaLedger(QuotaConfig(enabled=True, campaign_id="valid-counter-campaign", state_path=tmp_path / "q_cnt_val.json"))
    counter = GoogleGenAITokenCounter(
        api_key="test-key",
        dispatch_policy=policy,
        quota_ledger=ledger_valid,
    )
    assert counter is not None


@pytest.mark.asyncio
async def test_process_document_fails_closed_without_explicit_campaign_id_or_on_default(tmp_path: Path):
    """process_document fails closed before parsing/chunking when embedder has dispatch authorized without campaign ID."""
    from uuid import uuid4
    from app.models.documents import Document, IngestionJob
    from app.services.ingestion.parsing import ParsedSection
    from app.services.ingestion.processor import process_document

    doc_id = uuid4()
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

    ledger_default = QuotaLedger(QuotaConfig(enabled=True, campaign_id="default", state_path=tmp_path / "proc_q.json"))

    class DispatchAuthorizedEmbedder:
        model_name = "text-embedding-004"
        model_revision = "001"
        dispatch_policy = MockDispatchPolicy("google")
        quota_ledger = ledger_default

        def embed_texts(self, texts, **kwargs):
            raise AssertionError("Remote embed_texts must never be called when campaign ID validation fails")

    sections = [ParsedSection(text="Test section content", source_metadata={}, page=1)]
    success = await process_document(
        doc_id,
        parsed_sections=sections,
        session_factory=lambda: MockSession(),
        embedder=DispatchAuthorizedEmbedder(),
    )
    # process_document must fail closed: return False and record failed job status
    assert success is False
    assert job.status == "failed"


def test_quota_max_total_attempts_defaults_to_none_and_allows_unconstrained_lifetime(tmp_path: Path):
    """max_total_attempts defaults to None, removing the meaningless 1_000_000 lifetime ceiling."""
    cfg = QuotaConfig(enabled=True, campaign_id="test-camp", state_path=tmp_path / "q_ceiling.json")
    assert cfg.max_total_attempts is None

    # When max_total_attempts is explicitly None, reserve_attempt does not trip a lifetime ceiling
    ledger = QuotaLedger(cfg)
    aid = ledger.reserve_attempt("google", "text-embedding-004")
    assert aid is not None
    ledger.settle_attempt(aid, success=True)
