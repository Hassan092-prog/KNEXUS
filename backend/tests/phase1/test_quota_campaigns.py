"""Offline unit and integration tests for campaign-scoped quota budgets."""
from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

import httpx
import pytest

from app.api.dependencies import get_generation_service
from app.core.config import Settings, settings
from app.core.dispatch_policy import MockDispatchPolicy
from app.core.quota import QuotaConfig, QuotaExceededError, QuotaLedger
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


def test_missing_campaign_id_with_dispatch_policy_fails_closed(monkeypatch, tmp_path: Path):
    """Whenever provider dispatch is authorized, missing or empty QUOTA_CAMPAIGN_ID fails closed."""
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

    # 3. Non-empty string succeeds
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
