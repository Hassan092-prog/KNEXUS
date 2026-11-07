"""Tests for stale reservation recovery and terminal transition in QuotaLedger."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.quota import QuotaConfig, QuotaExceededError, QuotaLedger


def test_stale_reservation_recovery_with_injected_clock(tmp_path: Path):
    """An orphan blocks before in_flight_timeout_seconds and is recovered after it,

    using an injected clock with zero sleeping.
    """
    state_file = tmp_path / "ledger_stale.json"
    simulated_time = 1000.0

    def get_time():
        return simulated_time

    cfg = QuotaConfig(
        enabled=True,
        state_path=state_file,
        in_flight_timeout_seconds=30.0,
        lock_timeout_seconds=0.1,
        min_request_interval_seconds=0.0,
    )
    ledger = QuotaLedger(cfg, time_func=get_time)

    # 1. Make an active reservation at simulated_time = 1000.0
    aid = ledger.reserve_attempt("groq", "llama-3.3-70b-versatile")
    assert aid

    # 2. Advance clock by 10s (total elapsed = 10s < 30s timeout)
    simulated_time = 1010.0
    # Attempting to reserve while active and within timeout must fail with in-flight constraint
    with pytest.raises(QuotaExceededError, match="currently in flight"):
        ledger.reserve_attempt("groq", "llama-3.3-70b-versatile")

    # 3. Advance clock past the 30s timeout (elapsed = 35s >= 30s)
    simulated_time = 1035.0

    # Next reserve attempt recovers the stale reservation under the lock and issues a new reservation
    aid2 = ledger.reserve_attempt("groq", "llama-3.3-70b-versatile")
    assert aid2 != aid

    with open(state_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Verify active contains only the new reservation
    assert set(data["active_reservations"].keys()) == {aid2}

    # Verify settled_requests contains the recovered stale attempt as terminal expired_unresolved
    settled = data["settled_requests"]
    assert len(settled) == 1
    expired_rec = settled[0]
    assert expired_rec["attempt_id"] == aid
    assert expired_rec["terminal_state"] == "expired_unresolved"
    assert expired_rec["error"] == "expired_unresolved"
    assert expired_rec["success"] is False
    assert expired_rec["tokens_unresolved"] is True
    assert expired_rec["usage"] is None
    assert "in_flight_timeout_seconds" in expired_rec["reason"]

    # History preservation: total_attempts is 2 (the expired attempt + the new attempt)
    scope_info = data["scopes"]["groq:llama-3.3-70b-versatile"]
    assert scope_info["total_attempts"] == 2


def test_late_settle_attempt_for_expired_reservation(tmp_path: Path):
    """A late settle_attempt for an expired reservation attaches late usage without

    double-counting or changing the terminal failure outcome.
    """
    state_file = tmp_path / "ledger_late.json"
    simulated_time = 1000.0

    def get_time():
        return simulated_time

    cfg = QuotaConfig(
        enabled=True,
        state_path=state_file,
        in_flight_timeout_seconds=30.0,
        lock_timeout_seconds=0.1,
        min_request_interval_seconds=0.0,
    )
    ledger = QuotaLedger(cfg, time_func=get_time)

    aid = ledger.reserve_attempt("groq", "llama-3.3-70b-versatile")

    # Advance past timeout and recover
    simulated_time = 1040.0
    aid2 = ledger.reserve_attempt("groq", "llama-3.3-70b-versatile")

    # Now simulate the late arrival of a provider response for aid
    late_usage = {"prompt_tokens": 15, "completion_tokens": 5, "total_tokens": 20}
    ledger.settle_attempt(aid, usage=late_usage, success=True)

    with open(state_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Settled requests still has exactly 1 entry (aid); aid2 is still active
    settled = data["settled_requests"]
    assert len(settled) == 1
    rec = settled[0]
    assert rec["attempt_id"] == aid
    # Terminal outcome stays False
    assert rec["success"] is False
    assert rec["terminal_state"] == "expired_unresolved"
    # Late usage attached
    assert rec["late_usage"] == late_usage
    # Total attempts unchanged
    assert data["scopes"]["groq:llama-3.3-70b-versatile"]["total_attempts"] == 2


def test_racing_recovery_produces_exactly_one_transition(tmp_path: Path):
    """Two processes checking the ledger after timeout recover the orphan with exactly one transition."""
    state_file = tmp_path / "ledger_race.json"
    simulated_time = 1000.0

    def get_time():
        return simulated_time

    cfg = QuotaConfig(
        enabled=True,
        state_path=state_file,
        in_flight_timeout_seconds=10.0,
        lock_timeout_seconds=1.0,
        min_request_interval_seconds=0.0,
    )
    ledger1 = QuotaLedger(cfg, time_func=get_time)
    ledger2 = QuotaLedger(cfg, time_func=get_time)

    aid = ledger1.reserve_attempt("groq", "llama-3.3-70b-versatile")

    # Advance past timeout
    simulated_time = 1020.0

    # Process 1 reserves (triggers recovery)
    aid1 = ledger1.reserve_attempt("groq", "llama-3.3-70b-versatile")

    # Process 1 immediately settles aid1
    ledger1.settle_attempt(aid1, success=True)

    # Process 2 reserves
    aid2 = ledger2.reserve_attempt("groq", "llama-3.3-70b-versatile")

    with open(state_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    settled = data["settled_requests"]
    # Settled requests must contain exactly 1 expired_unresolved record for aid, and 1 record for aid1
    expired_records = [r for r in settled if r["attempt_id"] == aid]
    assert len(expired_records) == 1, "Expected exactly 1 transition for aid"
    assert expired_records[0]["terminal_state"] == "expired_unresolved"

