"""Tests for shared runtime quota controls, durability, and single in-flight concurrency."""
from multiprocessing import get_context
from pathlib import Path
import time
import pytest

from app.core.dispatch_policy import LiveInferenceBlockedError
from app.core.quota import (
    QuotaConfig,
    QuotaExceededError,
    QuotaLedger,
    QuotaStateCorruptError,
    RateLimitExceededError,
)


def test_quota_config_validation_rejects_booleans_and_negatives():
    with pytest.raises(ValueError, match="not boolean"):
        QuotaConfig(max_requests_per_minute=True)

    with pytest.raises(ValueError, match="positive integer"):
        QuotaConfig(max_requests_per_minute=-1)

    with pytest.raises(ValueError, match="non-negative finite number"):
        QuotaConfig(min_request_interval_seconds=float("nan"))


def test_quota_blocked_by_default(tmp_path: Path):
    ledger = QuotaLedger(QuotaConfig(enabled=False, state_path=tmp_path / "ledger.json"))
    with pytest.raises(LiveInferenceBlockedError, match="Live inference dispatch"):
        ledger.reserve_attempt("google", "gemini-embedding-001")


def test_quota_corrupt_state_fails_closed_never_resets(tmp_path: Path):
    state_file = tmp_path / "corrupt_ledger.json"

    # 1. Empty file
    state_file.write_text("", encoding="utf-8")
    ledger = QuotaLedger(QuotaConfig(enabled=True, state_path=state_file))
    with pytest.raises(QuotaStateCorruptError, match="empty"):
        ledger.reserve_attempt("google", "gemini-embedding-001")

    # 2. Corrupt JSON syntax
    state_file.write_text("{not valid json syntax...", encoding="utf-8")
    with pytest.raises(QuotaStateCorruptError, match="could not be read or parsed"):
        ledger.reserve_attempt("google", "gemini-embedding-001")

    # 3. Invalid schema / wrong types
    state_file.write_text('{"version": 1, "created_at": 100.0, "scopes": {}, "active_reservations": "wrong_type"}', encoding="utf-8")
    with pytest.raises(QuotaStateCorruptError, match="active_reservations must be a dict"):
        ledger.reserve_attempt("google", "gemini-embedding-001")

    # 4. Non-integer version (e.g. boolean)
    state_file.write_text('{"version": true, "scopes": {}}', encoding="utf-8")
    with pytest.raises(QuotaStateCorruptError, match="non-integer"):
        ledger.reserve_attempt("google", "gemini-embedding-001")

    # 5. Contradictory counter in scopes
    state_file.write_text(
        '{"version": 1, "created_at": 100.0, "scopes": {"g:m": {"total_attempts": 5, "rate_limited": false, "last_dispatch_time": 0}}, "active_reservations": {}, "settled_requests": []}',
        encoding="utf-8"
    )
    with pytest.raises(QuotaStateCorruptError, match="Contradictory counters"):
        ledger.reserve_attempt("g", "m")

    # Confirm counters were not reset to 0; file remains untouched
    assert "Contradictory counters" in state_file.read_text(encoding="utf-8") or '"total_attempts": 5' in state_file.read_text(encoding="utf-8")


def _worker_hold_reservation(state_path: str, proc1_has_lock, proc1_can_settle, result_queue):
    try:
        config = QuotaConfig(enabled=True, state_path=Path(state_path), min_request_interval_seconds=0.0)
        ledger = QuotaLedger(config)
        attempt_id = ledger.reserve_attempt("groq", "openai/gpt-oss-120b")
        result_queue.put(("p1_reserved", attempt_id))
        proc1_has_lock.set()

        if not proc1_can_settle.wait(timeout=5.0):
            result_queue.put(("p1_error", "timeout waiting for can_settle"))
            return

        ledger.settle_attempt(
            attempt_id,
            usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            success=True,
        )
        result_queue.put(("p1_settled", attempt_id))
    except Exception as exc:
        result_queue.put(("p1_exception", f"{type(exc).__name__}: {exc}"))


def _worker_try_conflicting_reservation(state_path: str, proc1_has_lock, proc2_tried, proc2_can_reserve, result_queue):
    try:
        if not proc1_has_lock.wait(timeout=5.0):
            result_queue.put(("p2_error", "timeout waiting for p1 lock"))
            return

        # Attempt conflicting reservation with short lock timeout: should fail immediately due to in-flight request
        config = QuotaConfig(
            enabled=True,
            state_path=Path(state_path),
            lock_timeout_seconds=0.15,
            min_request_interval_seconds=0.0,
        )
        ledger = QuotaLedger(config)

        try:
            ledger.reserve_attempt("groq", "openai/gpt-oss-120b")
            result_queue.put(("p2_unexpected_success", None))
        except QuotaExceededError as q_exc:
            result_queue.put(("p2_caught_expected_conflict", str(q_exc)))
        finally:
            proc2_tried.set()

        if not proc2_can_reserve.wait(timeout=5.0):
            result_queue.put(("p2_error", "timeout waiting for can_reserve"))
            return

        # After P1 settles, reservation must succeed
        att2 = ledger.reserve_attempt("groq", "openai/gpt-oss-120b")
        ledger.settle_attempt(
            att2,
            usage={"prompt_tokens": 20, "completion_tokens": 10, "total_tokens": 30},
            success=True,
        )
        result_queue.put(("p2_settled", att2))
    except Exception as exc:
        result_queue.put(("p2_exception", f"{type(exc).__name__}: {exc}"))


def test_quota_real_separate_processes_single_in_flight(tmp_path: Path):
    # Real OS process concurrency test sharing a single state/lock file
    state_file = tmp_path / "shared_process_ledger.json"
    ctx = get_context("spawn")

    proc1_has_lock = ctx.Event()
    proc1_can_settle = ctx.Event()
    proc2_tried = ctx.Event()
    proc2_can_reserve = ctx.Event()
    result_queue = ctx.Queue()

    p1 = ctx.Process(
        target=_worker_hold_reservation,
        args=(str(state_file), proc1_has_lock, proc1_can_settle, result_queue),
    )
    p2 = ctx.Process(
        target=_worker_try_conflicting_reservation,
        args=(str(state_file), proc1_has_lock, proc2_tried, proc2_can_reserve, result_queue),
    )

    try:
        p1.start()
        p2.start()

        # Wait until P2 has verified that P1's in-flight request blocked it
        assert proc2_tried.wait(timeout=5.0), "P2 failed to attempt conflicting reservation"

        # Allow P1 to finish and settle
        proc1_can_settle.set()
        p1.join(timeout=5.0)
        assert p1.exitcode == 0, f"P1 exited with code {p1.exitcode}"

        # Now allow P2 to reserve and settle
        proc2_can_reserve.set()
        p2.join(timeout=5.0)
        assert p2.exitcode == 0, f"P2 exited with code {p2.exitcode}"

    finally:
        for p in (p1, p2):
            if p.is_alive():
                p.terminate()
                p.join(timeout=1.0)

    # Collect outcomes from queue
    results = {}
    while not result_queue.empty():
        k, v = result_queue.get_nowait()
        results[k] = v

    assert "p1_reserved" in results
    assert "p1_settled" in results
    assert "p2_caught_expected_conflict" in results
    assert "Single in-flight constraint violated" in results["p2_caught_expected_conflict"]
    assert "p2_settled" in results

    # Verify durable restart retention and counters
    ledger_verify = QuotaLedger(QuotaConfig(enabled=True, state_path=state_file))
    state = ledger_verify._load_state()
    assert len(state["active_reservations"]) == 0
    assert len(state["settled_requests"]) == 2
    scope_data = state["scopes"]["groq:openai/gpt-oss-120b"]
    assert scope_data["total_attempts"] == 2


def test_quota_distinct_provider_scopes(tmp_path: Path):
    state_file = tmp_path / "scoped_ledger.json"
    config = QuotaConfig(
        enabled=True,
        state_path=state_file,
        min_request_interval_seconds=0.0,
    )
    ledger = QuotaLedger(config)

    # Trip rate limit on Groq
    groq_id = ledger.reserve_attempt("groq", "openai/gpt-oss-120b")
    ledger.settle_attempt(
        groq_id,
        status_code=429,
        error="HTTP 429 Rate Limit on Groq",
        success=False,
    )

    # Groq must now be blocked
    with pytest.raises(RateLimitExceededError, match="rate limit active"):
        ledger.reserve_attempt("groq", "openai/gpt-oss-120b")

    # Google scope must remain unaffected and available
    google_id = ledger.reserve_attempt("google", "gemini-embedding-001")
    assert google_id is not None
    ledger.settle_attempt(google_id, success=True)


def test_quota_duplicate_and_unknown_settlement_rejected(tmp_path: Path):
    state_file = tmp_path / "ledger.json"
    config = QuotaConfig(
        enabled=True,
        state_path=state_file,
        min_request_interval_seconds=0.0,
    )
    ledger = QuotaLedger(config)

    # Unknown attempt ID
    with pytest.raises(KeyError, match="Unknown attempt ID"):
        ledger.settle_attempt("nonexistent-uuid")

    # Valid reservation and first settlement
    attempt_id = ledger.reserve_attempt("google", "gemini-embedding-001")
    ledger.settle_attempt(attempt_id, success=True)

    # Duplicate settlement
    with pytest.raises(ValueError, match="Duplicate settlement"):
        ledger.settle_attempt(attempt_id, success=True)


def test_quota_malformed_usage_marked_unresolved(tmp_path: Path):
    state_file = tmp_path / "ledger.json"
    config = QuotaConfig(
        enabled=True,
        state_path=state_file,
        min_request_interval_seconds=0.0,
    )
    ledger = QuotaLedger(config)

    # 1. Negative values
    id1 = ledger.reserve_attempt("google", "gemini-embedding-001")
    ledger.settle_attempt(
        id1,
        usage={"prompt_tokens": -10, "completion_tokens": 5, "total_tokens": -5},
        success=True,
    )

    # 2. Boolean values in usage
    id2 = ledger.reserve_attempt("google", "gemini-embedding-001")
    ledger.settle_attempt(
        id2,
        usage={"prompt_tokens": True, "completion_tokens": 5, "total_tokens": 6},
        success=True,
    )

    # 3. Mathematically contradictory usage (prompt + completion != total)
    id3 = ledger.reserve_attempt("google", "gemini-embedding-001")
    ledger.settle_attempt(
        id3,
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 999},
        success=True,
    )

    # 4. Missing fields
    id4 = ledger.reserve_attempt("google", "gemini-embedding-001")
    ledger.settle_attempt(
        id4,
        usage={"prompt_tokens": 10},
        success=True,
    )

    state = ledger._load_state()
    for rec in state["settled_requests"]:
        assert rec["usage_valid"] is False
        assert rec["tokens_unresolved"] is True
        assert "error" in rec["usage"]


def test_quota_restart_retention(tmp_path: Path):
    state_file = tmp_path / "ledger.json"
    config = QuotaConfig(
        enabled=True,
        state_path=state_file,
        min_request_interval_seconds=0.0,
    )
    ledger_instance_1 = QuotaLedger(config)
    attempt_id = ledger_instance_1.reserve_attempt("google", "gemini-embedding-001")

    # New instance simulating restart
    ledger_instance_2 = QuotaLedger(config)
    state = ledger_instance_2._load_state()
    assert attempt_id in state["active_reservations"]
