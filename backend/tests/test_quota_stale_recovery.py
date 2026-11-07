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
def test_quota_config_refuses_insufficient_in_flight_timeout():
    """Settings and QuotaConfig refuse in_flight_timeout_seconds not greater than longest deadline + margin."""
    from pydantic import ValidationError
    from app.core.config import Settings

    # Longest deadline = max(30.0, 20.0, 30.0) = 30.0. Margin = 5.0. Min required > 35.0.
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            GENERATION_TIMEOUT=30.0,
            EMBEDDING_TIMEOUT=20.0,
            EMBEDDING_VALIDATION_DEADLINE_SECONDS=30.0,
            QUOTA_IN_FLIGHT_TIMEOUT_SECONDS=35.0,  # <= 35.0 is refused
        )
    assert "must be strictly greater than longest provider deadline" in str(exc_info.value)

    cfg = QuotaConfig(in_flight_timeout_seconds=35.0)
    with pytest.raises(ValueError, match="must be strictly greater than longest deadline"):
        cfg.validate_against_deadlines(max_deadline=30.0, safety_margin=5.0)


def test_late_settlement_carrying_status_429_trips_rate_limit(tmp_path: Path):
    """A late settlement for an expired attempt carrying HTTP 429 must trip the scope rate limit."""
    from app.core.quota import RateLimitExceededError

    state_file = tmp_path / "ledger_late_429.json"
    fake_time = 1000.0
    def clock():
        return fake_time

    cfg = QuotaConfig(
        enabled=True,
        state_path=state_file,
        in_flight_timeout_seconds=10.0,
        lock_timeout_seconds=0.05,
    )
    ledger = QuotaLedger(cfg, time_func=clock)

    # 1. Reserve attempt
    aid = ledger.reserve_attempt("google", "gemini-embedding-001")

    # 2. Advance clock beyond in_flight_timeout_seconds so attempt expires
    fake_time += 15.0

    # 3. Next reservation triggers recovery of stale attempt to expired_unresolved
    aid2 = ledger.reserve_attempt("google", "gemini-embedding-001")

    # 4. Late settlement for expired attempt arrives carrying status_code=429
    ledger.settle_attempt(
        aid,
        status_code=429,
        success=False,
        error="http_429_late",
    )

    # Settle aid2 normally so active reservations is empty
    ledger.settle_attempt(aid2, success=True)

    # 5. Subsequent reservation must raise RateLimitExceededError because late 429 tripped the tripwire
    with pytest.raises(RateLimitExceededError, match="rate limit active"):
        ledger.reserve_attempt("google", "gemini-embedding-001")


def _worker_reserve_settle(state_path_str: str, attempts: int, result_queue):
    import time
    from pathlib import Path
    from app.core.quota import QuotaConfig, QuotaLedger, QuotaError
    cfg = QuotaConfig(
        enabled=True,
        state_path=Path(state_path_str),
        lock_timeout_seconds=2.0,
        min_request_interval_seconds=0.0,
    )
    ledger = QuotaLedger(cfg)
    successes = 0
    errors = 0
    for _ in range(attempts):
        try:
            aid = ledger.reserve_attempt("groq", "mp-test-model")
            time.sleep(0.01)
            ledger.settle_attempt(aid, success=True)
            successes += 1
        except QuotaError:
            errors += 1
    result_queue.put((successes, errors))


def test_true_multiprocessing_race_against_real_file_lock(tmp_path: Path):
    """Separate OS processes race to reserve and settle against the real file lock."""
    import multiprocessing

    state_file = tmp_path / "mp_race_ledger.json"
    queue = multiprocessing.Queue()
    num_processes = 3
    attempts_per_process = 5

    processes = [
        multiprocessing.Process(
            target=_worker_reserve_settle,
            args=(str(state_file), attempts_per_process, queue),
        )
        for _ in range(num_processes)
    ]

    for p in processes:
        p.start()
    for p in processes:
        p.join(timeout=10.0)
        assert not p.is_alive(), "Process hung or timed out on file lock"

    results = [queue.get_nowait() for _ in range(num_processes)]
    total_successes = sum(r[0] for r in results)
    total_errors = sum(r[1] for r in results)

    assert total_successes > 0, "Expected at least one successful reserve/settle"

    with open(state_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Exactly total_successes in settled_requests and 0 remaining in active_reservations
    assert len(data.get("active_reservations", {})) == 0
    assert len(data.get("settled_requests", [])) == total_successes
