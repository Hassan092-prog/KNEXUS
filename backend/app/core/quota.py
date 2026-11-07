"""Shared runtime quota controls and durable rate-limit authority.

Enforces cross-process single in-flight concurrency, durable fail-closed state,
distinct provider/model quota scopes, atomic reserve-before-dispatch, and
fail-closed rate limit handling without silent retries.

Limitation notice: This ledger enforces request controls (rate limits, interval
pacing, attempt ceilings, single in-flight concurrency, and 429 fail-closed tripwire),
but server-side token budget enforcement cannot be validated offline because hosted
token counting is unresolved. Dispatch remains strictly blocked by default.
"""
from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import sys
import time
from typing import Any
import uuid

from app.core.dispatch_policy import BlockedLiveDispatchPolicy, LiveInferenceBlockedError


class QuotaError(Exception):
    """Base exception for runtime quota enforcement."""


class QuotaCampaignError(QuotaError, ValueError):
    """Raised when dispatch is authorized but campaign ID is missing, blank, or 'default'."""


class QuotaExceededError(QuotaError):
    """Raised when request, token, or concurrency limits are exhausted."""


class RateLimitExceededError(QuotaError):
    """Raised when provider returned HTTP 429; no silent retries permitted."""


class QuotaStateCorruptError(QuotaError):
    """Raised when durable quota state is corrupt, unreadable, or invalid."""


def _is_strict_int(val: Any) -> bool:
    return isinstance(val, int) and not isinstance(val, bool)


def _is_finite_number(val: Any) -> bool:
    return isinstance(val, (int, float)) and not isinstance(val, bool) and math.isfinite(float(val))


@dataclass(frozen=True)
class QuotaConfig:
    """Configuration for durable quota management with campaign-scoped budgets."""

    enabled: bool = False
    campaign_id: str = "default"
    max_campaign_attempts: int | None = 500
    max_requests_per_minute: int = 30
    max_requests_per_day: int = 1000
    max_total_attempts: int | None = None
    min_request_interval_seconds: float = 2.0
    in_flight_timeout_seconds: float = 60.0
    lock_timeout_seconds: float = 10.0
    state_path: Path | None = None

    def __post_init__(self):
        if not isinstance(self.campaign_id, str):
            raise ValueError("campaign_id must be a string")
        if self.max_campaign_attempts is not None:
            if not _is_strict_int(self.max_campaign_attempts) or self.max_campaign_attempts < 0:
                raise ValueError("max_campaign_attempts must be a non-negative integer (not boolean)")
        if not _is_strict_int(self.max_requests_per_minute) or self.max_requests_per_minute <= 0:
            raise ValueError("max_requests_per_minute must be a positive integer (not boolean)")
        if not _is_strict_int(self.max_requests_per_day) or self.max_requests_per_day <= 0:
            raise ValueError("max_requests_per_day must be a positive integer (not boolean)")
        if self.max_total_attempts is not None:
            if not _is_strict_int(self.max_total_attempts) or self.max_total_attempts < 0:
                raise ValueError("max_total_attempts must be a non-negative integer (not boolean)")
        if not _is_finite_number(self.min_request_interval_seconds) or self.min_request_interval_seconds < 0:
            raise ValueError("min_request_interval_seconds must be a non-negative finite number")
        if not _is_finite_number(self.in_flight_timeout_seconds) or self.in_flight_timeout_seconds <= 0:
            raise ValueError("in_flight_timeout_seconds must be a positive finite number")
        if not _is_finite_number(self.lock_timeout_seconds) or self.lock_timeout_seconds <= 0:
            raise ValueError("lock_timeout_seconds must be a positive finite number")

    def validate_against_deadlines(self, max_deadline: float, safety_margin: float = 5.0) -> None:
        min_required = float(max_deadline) + float(safety_margin)
        if float(self.in_flight_timeout_seconds) <= min_required:
            raise ValueError(
                f"in_flight_timeout_seconds ({self.in_flight_timeout_seconds}s) must be strictly "
                f"greater than longest deadline ({max_deadline}s) + safety margin ({safety_margin}s) = {min_required}s "
                f"to prevent concurrent dispatches while an active request is legitimately in flight."
            )


class QuotaLedger:
    """Durable quota authority with cross-process locking and single in-flight gating."""

    def __init__(
        self,
        config: QuotaConfig | None = None,
        *,
        time_func: Any | None = None,
    ) -> None:
        self.config = config or QuotaConfig()
        self.campaign_id = self.config.campaign_id
        self._time = time_func or time.time
        if self.config.state_path is not None:
            self._default_state_path = self.config.state_path
        else:
            try:
                from app.core.config import settings
                self._default_state_path = settings.QUOTA_STATE_PATH
            except Exception:
                self._default_state_path = Path(".knexus-private-storage") / "quota_state.json"

    @property
    def state_path(self) -> Path:
        return self.config.state_path or self._default_state_path

    @property
    def lock_path(self) -> Path:
        return self.state_path.with_suffix(".lock")

    def _acquire_file_lock(self, timeout: float):
        start = time.monotonic()
        lock_path = self.lock_path
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        if sys.platform != "win32":
            import fcntl

            fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR, 0o600)
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    return fd
                except (BlockingIOError, OSError):
                    if time.monotonic() - start >= timeout:
                        os.close(fd)
                        raise TimeoutError(
                            f"Could not acquire quota lock on {lock_path} within {timeout}s"
                        )
                    time.sleep(0.02)
        else:
            import msvcrt

            fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
            while True:
                try:
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    return fd
                except (BlockingIOError, OSError):
                    if time.monotonic() - start >= timeout:
                        os.close(fd)
                        raise TimeoutError(
                            f"Could not acquire quota lock on {lock_path} within {timeout}s"
                        )
                    time.sleep(0.02)

    def _release_file_lock(self, fd: int) -> None:
        if fd < 0:
            return
        if sys.platform != "win32":
            import fcntl

            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                os.close(fd)
            except OSError:
                pass
        else:
            import msvcrt

            try:
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            try:
                os.close(fd)
            except OSError:
                pass

    def _validate_state_schema(self, data: Any) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise QuotaStateCorruptError("Quota state root is not a dict")
        # Migrate legacy records on read without destructively modifying on-disk records
        active_res = data.get("active_reservations")
        if isinstance(active_res, dict):
            for rec in active_res.values():
                if isinstance(rec, dict) and ("campaign_id" not in rec or not rec["campaign_id"]):
                    rec["campaign_id"] = "legacy"
        settled_req = data.get("settled_requests")
        if isinstance(settled_req, list):
            for rec in settled_req:
                if isinstance(rec, dict) and ("campaign_id" not in rec or not rec["campaign_id"]):
                    rec["campaign_id"] = "legacy"
        if data.get("version") != 1 or not _is_strict_int(data.get("version")):
            raise QuotaStateCorruptError(f"Unsupported or non-integer quota state version: {data.get('version')}")
        if not _is_finite_number(data.get("created_at")) or data["created_at"] <= 0:
            raise QuotaStateCorruptError("created_at must be a positive finite timestamp")
        if not isinstance(data.get("scopes"), dict):
            raise QuotaStateCorruptError("scopes must be a dict")
        if not isinstance(data.get("active_reservations"), dict):
            raise QuotaStateCorruptError("active_reservations must be a dict")
        if not isinstance(data.get("settled_requests"), list):
            raise QuotaStateCorruptError("settled_requests must be a list")

        # Validate scopes
        scopes = data["scopes"]
        for scope_key, s_data in scopes.items():
            if not isinstance(scope_key, str) or ":" not in scope_key or not scope_key.strip():
                raise QuotaStateCorruptError(f"Malformed scope identity: {scope_key!r}")
            if not isinstance(s_data, dict):
                raise QuotaStateCorruptError(f"Scope data for '{scope_key}' must be a dict")
            if not _is_strict_int(s_data.get("total_attempts")) or s_data["total_attempts"] < 0:
                raise QuotaStateCorruptError(f"total_attempts in scope '{scope_key}' must be a non-negative integer")
            if not isinstance(s_data.get("rate_limited"), bool):
                raise QuotaStateCorruptError(f"rate_limited in scope '{scope_key}' must be a boolean")
            if s_data.get("rate_limit_reason") is not None and not isinstance(s_data.get("rate_limit_reason"), str):
                raise QuotaStateCorruptError(f"rate_limit_reason in scope '{scope_key}' must be string or None")
            if not _is_finite_number(s_data.get("last_dispatch_time")) or s_data["last_dispatch_time"] < 0:
                raise QuotaStateCorruptError(f"last_dispatch_time in scope '{scope_key}' must be non-negative finite number")

        # Validate active reservations
        active_ids: set[str] = set()
        active = data["active_reservations"]
        for att_id, a_data in active.items():
            if not isinstance(att_id, str) or not att_id.strip():
                raise QuotaStateCorruptError("Active attempt ID must be non-empty string")
            active_ids.add(att_id)
            if not isinstance(a_data, dict):
                raise QuotaStateCorruptError(f"Reservation data for '{att_id}' must be a dict")
            if not _is_finite_number(a_data.get("reserved_at")) or a_data["reserved_at"] <= 0:
                raise QuotaStateCorruptError(f"reserved_at in '{att_id}' must be positive finite timestamp")
            if not isinstance(a_data.get("provider"), str) or not a_data["provider"].strip():
                raise QuotaStateCorruptError(f"provider in '{att_id}' must be non-empty string")
            if not isinstance(a_data.get("model"), str) or not a_data["model"].strip():
                raise QuotaStateCorruptError(f"model in '{att_id}' must be non-empty string")
            scope = a_data.get("scope")
            if not isinstance(scope, str) or scope != f"{a_data['provider']}:{a_data['model']}":
                raise QuotaStateCorruptError(f"Scope mismatch in reservation '{att_id}'")
            if scope not in scopes:
                raise QuotaStateCorruptError(f"Reservation '{att_id}' references unknown scope '{scope}'")

        # Validate settled requests and check for duplicate/contradictory IDs
        settled_ids: set[str] = set()
        settled = data["settled_requests"]
        for idx, rec in enumerate(settled):
            if not isinstance(rec, dict):
                raise QuotaStateCorruptError(f"Settled request record {idx} must be a dict")
            att_id = rec.get("attempt_id")
            if not isinstance(att_id, str) or not att_id.strip():
                raise QuotaStateCorruptError(f"Missing attempt_id in settled record {idx}")
            if att_id in settled_ids:
                raise QuotaStateCorruptError(f"Duplicate attempt_id '{att_id}' in settled requests")
            settled_ids.add(att_id)

            if att_id in active_ids:
                raise QuotaStateCorruptError(
                    f"Contradictory state: attempt '{att_id}' is present in both active and settled sets"
                )

            scope = rec.get("scope")
            if not isinstance(scope, str) or scope not in scopes:
                raise QuotaStateCorruptError(f"Settled record '{att_id}' references unknown scope '{scope}'")
            if not isinstance(rec.get("provider"), str) or not isinstance(rec.get("model"), str):
                raise QuotaStateCorruptError(f"Missing provider/model in settled record '{att_id}'")
            if not _is_finite_number(rec.get("reserved_at")) or rec["reserved_at"] <= 0:
                raise QuotaStateCorruptError(f"reserved_at in settled record '{att_id}' must be positive timestamp")
            if not _is_finite_number(rec.get("timestamp")) or rec["timestamp"] < rec["reserved_at"]:
                raise QuotaStateCorruptError(f"timestamp in settled record '{att_id}' cannot precede reserved_at")
            if not isinstance(rec.get("success"), bool):
                raise QuotaStateCorruptError(f"success in settled record '{att_id}' must be boolean")
            if not isinstance(rec.get("usage_valid"), bool) or not isinstance(rec.get("tokens_unresolved"), bool):
                raise QuotaStateCorruptError(f"usage_valid and tokens_unresolved must be boolean in '{att_id}'")

            # Validate verified usage structure
            if rec["usage_valid"] is True:
                if rec["tokens_unresolved"] is not False:
                    raise QuotaStateCorruptError(f"tokens_unresolved must be False when usage_valid is True in '{att_id}'")
                u = rec.get("usage")
                if not isinstance(u, dict):
                    raise QuotaStateCorruptError(f"Verified usage in '{att_id}' must be a dict")
                p = u.get("prompt_tokens")
                c = u.get("completion_tokens")
                t = u.get("total_tokens")
                if (
                    not _is_strict_int(p) or p < 0
                    or not _is_strict_int(c) or c < 0
                    or not _is_strict_int(t) or t < 0
                    or p + c != t
                ):
                    raise QuotaStateCorruptError(f"Contradictory or malformed verified usage in '{att_id}'")

        # Verify counter consistency per scope
        for scope_key, s_data in scopes.items():
            expected_total = s_data["total_attempts"]
            count_active = sum(1 for a in active.values() if a.get("scope") == scope_key)
            count_settled = sum(1 for s in settled if s.get("scope") == scope_key)
            if count_active + count_settled != expected_total:
                raise QuotaStateCorruptError(
                    f"Contradictory counters for scope '{scope_key}': total_attempts={expected_total} "
                    f"does not match active({count_active}) + settled({count_settled})"
                )

        return data

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {
                "version": 1,
                "created_at": self._time(),
                "scopes": {},
                "active_reservations": {},
                "settled_requests": [],
            }
        try:
            with open(self.state_path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    raise QuotaStateCorruptError("Quota state file is empty")
                raw = json.loads(content)
        except Exception as exc:
            if isinstance(exc, QuotaStateCorruptError):
                raise
            raise QuotaStateCorruptError(
                f"Quota state file at {self.state_path} could not be read or parsed: {exc}"
            ) from exc

        return self._validate_state_schema(raw)

    def _save_state(self, state: dict[str, Any]) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.state_path.with_suffix(f".tmp.{uuid.uuid4().hex}")
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_path, self.state_path)

    def reserve_attempt(self, provider: str, model: str) -> str:
        """Atomically reserve a dispatch slot.

        Enforces:
        1. Authorization check: if config.enabled is False, fails before any dispatch.
        2. Scope separation: rate limits and quotas are distinct per (provider, model).
        3. Single in-flight across processes: if another reservation is active, blocks/fails.
        4. Request limits (RPM, RPD, total attempts, 429 tripwire).
        """
        if not self.config.enabled:
            raise LiveInferenceBlockedError(
                f"Live inference dispatch to '{provider}' is unauthorized. Paid API budget is $0."
            )

        scope_key = f"{provider}:{model}"
        start_wait = time.monotonic()

        while True:
            fd = self._acquire_file_lock(self.config.lock_timeout_seconds)
            should_retry = False
            try:
                state = self._load_state()
                now = self._time()

                scopes: dict[str, Any] = state.setdefault("scopes", {})
                scope_info = scopes.setdefault(scope_key, {
                    "total_attempts": 0,
                    "rate_limited": False,
                    "rate_limit_reason": None,
                    "last_dispatch_time": 0.0,
                })

                if scope_info.get("rate_limited"):
                    reason = scope_info.get("rate_limit_reason") or "HTTP 429 received previously"
                    raise RateLimitExceededError(
                        f"Scope '{scope_key}' rate limit active: {reason}. No silent retries permitted."
                    )

                active: dict[str, Any] = state.setdefault("active_reservations", {})
                settled: list[dict[str, Any]] = state.setdefault("settled_requests", [])

                # Enforce in_flight_timeout_seconds: transition stale active reservations
                # to terminal expired_unresolved records under the lock at reserve time.
                stale_ids = []
                for aid, item in list(active.items()):
                    reserved_at = item.get("reserved_at", 0.0)
                    if now - reserved_at >= self.config.in_flight_timeout_seconds:
                        stale_ids.append(aid)

                for aid in stale_ids:
                    res = active.pop(aid)
                    scope_k = res.get("scope", f"{res.get('provider')}:{res.get('model')}")
                    expired_record = {
                        "attempt_id": aid,
                        "scope": scope_k,
                        "provider": res.get("provider"),
                        "model": res.get("model"),
                        "reserved_at": res.get("reserved_at"),
                        "timestamp": now,
                        "success": False,
                        "error": "expired_unresolved",
                        "terminal_state": "expired_unresolved",
                        "status_code": None,
                        "usage": None,
                        "usage_valid": False,
                        "tokens_unresolved": True,
                        "expired_at": now,
                        "campaign_id": res.get("campaign_id", "legacy"),
                        "reason": (
                            f"Active reservation exceeded in_flight_timeout_seconds "
                            f"({self.config.in_flight_timeout_seconds}s)"
                        ),
                    }
                    settled.append(expired_record)

                if active:
                    in_flight_id = next(iter(active.keys()))
                    in_flight_item = active[in_flight_id]
                    elapsed = now - in_flight_item.get("reserved_at", 0)

                    if time.monotonic() - start_wait >= self.config.lock_timeout_seconds:
                        raise QuotaExceededError(
                            f"Single in-flight constraint violated: request '{in_flight_id}' is currently "
                            f"in flight (elapsed {elapsed:.1f}s). Concurrent dispatches rejected across processes."
                        )
                    should_retry = True
                else:
                    settled: list[dict[str, Any]] = state.setdefault("settled_requests", [])

                    # Count total attempts per (campaign_id, scope)
                    campaign_id = self.campaign_id
                    active_campaign = sum(
                        1 for r in active.values()
                        if r.get("scope") == scope_key and r.get("campaign_id", "legacy") == campaign_id
                    )
                    settled_campaign = sum(
                        1 for r in settled
                        if r.get("scope") == scope_key and r.get("campaign_id", "legacy") == campaign_id
                    )
                    total_campaign_attempts = active_campaign + settled_campaign
                    if (
                        self.config.max_campaign_attempts is not None
                        and total_campaign_attempts >= self.config.max_campaign_attempts
                    ):
                        raise QuotaExceededError(
                            f"Scope '{scope_key}' campaign '{campaign_id}' attempt limit "
                            f"({total_campaign_attempts}/{self.config.max_campaign_attempts}) reached."
                        )

                    total_attempts = scope_info.get("total_attempts", 0)
                    if (
                        self.config.max_total_attempts is not None
                        and total_attempts >= self.config.max_total_attempts
                    ):
                        raise QuotaExceededError(
                            f"Scope '{scope_key}' total attempt ceiling ({self.config.max_total_attempts}) reached."
                        )
                    recent_60s = 0
                    daily = 0
                    for rec in settled:
                        if rec.get("scope") == scope_key:
                            ts = rec.get("timestamp", 0)
                            if now - ts <= 60:
                                recent_60s += 1
                            if now - ts <= 86400:
                                daily += 1

                    if recent_60s >= self.config.max_requests_per_minute:
                        raise QuotaExceededError(
                            f"Scope '{scope_key}' requests per minute quota exceeded ({recent_60s}/{self.config.max_requests_per_minute})"
                        )
                    if daily >= self.config.max_requests_per_day:
                        raise QuotaExceededError(
                            f"Scope '{scope_key}' daily requests quota exceeded ({daily}/{self.config.max_requests_per_day})"
                        )

                    last_dispatch = scope_info.get("last_dispatch_time", 0.0)
                    if now - last_dispatch < self.config.min_request_interval_seconds:
                        sleep_needed = self.config.min_request_interval_seconds - (now - last_dispatch)
                        time.sleep(sleep_needed)
                        now = self._time()

                    attempt_id = str(uuid.uuid4())
                    active[attempt_id] = {
                        "reserved_at": now,
                        "provider": provider,
                        "model": model,
                        "scope": scope_key,
                        "campaign_id": self.campaign_id,
                    }
                    scope_info["total_attempts"] = total_attempts + 1
                    scope_info["last_dispatch_time"] = now
                    self._save_state(state)
                    return attempt_id
            finally:
                self._release_file_lock(fd)

            if should_retry:
                time.sleep(0.05)

    def settle_attempt(
        self,
        attempt_id: str,
        *,
        usage: dict[str, Any] | None = None,
        success: bool = True,
        error: str | None = None,
        status_code: int | None = None,
    ) -> None:
        """Settle a reservation.

        Rejects unknown or duplicate attempt IDs. Validates usage without inventing
        unresolved token bounds. Sets rate-limited on 429 for the specific scope.
        """
        fd = self._acquire_file_lock(self.config.lock_timeout_seconds)
        try:
            state = self._load_state()
            active: dict[str, Any] = state.setdefault("active_reservations", {})
            settled: list[dict[str, Any]] = state.setdefault("settled_requests", [])

            # Reject duplicate settlements or handle late settlement for expired attempts
            for s in settled:
                if s.get("attempt_id") == attempt_id:
                    if s.get("terminal_state") == "expired_unresolved":
                        # Late settlement for expired attempt: do not double-count!
                        # Attach late usage if valid, without changing the terminal outcome (success remains False)
                        if usage is not None and isinstance(usage, dict) and s.get("late_usage") is None:
                            p_tok = usage.get("prompt_tokens")
                            c_tok = usage.get("completion_tokens")
                            t_tok = usage.get("total_tokens")
                            if (
                                _is_strict_int(p_tok) and p_tok >= 0
                                and _is_strict_int(c_tok) and c_tok >= 0
                                and _is_strict_int(t_tok) and t_tok >= 0
                                and p_tok + c_tok == t_tok
                            ):
                                s["late_usage"] = {
                                    "prompt_tokens": p_tok,
                                    "completion_tokens": c_tok,
                                    "total_tokens": t_tok,
                                }
                        # Late settlement carrying status 429 must still trip the rate-limit tripwire!
                        if status_code == 429 or (error and "429" in str(error)):
                            scope_k = s.get("scope") or f"{s.get('provider')}:{s.get('model')}"
                            scopes = state.setdefault("scopes", {})
                            scope_info = scopes.setdefault(scope_k, {})
                            scope_info["rate_limited"] = True
                            scope_info["rate_limit_reason"] = error or "HTTP 429 Too Many Requests (late settlement)"
                        self._save_state(state)
                        return
                    raise ValueError(f"Duplicate settlement: attempt '{attempt_id}' is already settled.")

            # Reject unknown attempts
            if attempt_id not in active:
                raise KeyError(f"Unknown attempt ID '{attempt_id}': no active reservation found.")

            res = active.pop(attempt_id)
            scope_key = res.get("scope", f"{res.get('provider')}:{res.get('model')}")
            now = self._time()

            # Validate usage without inventing false counts
            parsed_usage: dict[str, Any] | None = None
            usage_valid = False

            if usage is not None and isinstance(usage, dict):
                p_tok = usage.get("prompt_tokens")
                c_tok = usage.get("completion_tokens")
                t_tok = usage.get("total_tokens")
                # Usage must not contain booleans, negative values, or mathematical contradictions
                if (
                    _is_strict_int(p_tok) and p_tok >= 0
                    and _is_strict_int(c_tok) and c_tok >= 0
                    and _is_strict_int(t_tok) and t_tok >= 0
                    and p_tok + c_tok == t_tok
                ):
                    parsed_usage = {
                        "prompt_tokens": p_tok,
                        "completion_tokens": c_tok,
                        "total_tokens": t_tok,
                    }
                    usage_valid = True
                else:
                    parsed_usage = {"raw": str(usage), "error": "malformed_negative_or_inconsistent_values"}
                    usage_valid = False
            else:
                parsed_usage = None
                usage_valid = False

            record = {
                "attempt_id": attempt_id,
                "scope": scope_key,
                "provider": res.get("provider"),
                "model": res.get("model"),
                "reserved_at": res.get("reserved_at"),
                "timestamp": now,
                "success": success,
                "error": error,
                "status_code": status_code,
                "usage": parsed_usage,
                "usage_valid": usage_valid,
                "tokens_unresolved": not usage_valid,
                "campaign_id": res.get("campaign_id", self.campaign_id),
            }
            settled.append(record)

            # Scope-specific rate-limit trigger on 429
            if status_code == 429 or (error and "429" in error):
                scopes = state.setdefault("scopes", {})
                scope_info = scopes.setdefault(scope_key, {})
                scope_info["rate_limited"] = True
                scope_info["rate_limit_reason"] = error or "HTTP 429 Too Many Requests"

            self._save_state(state)
        finally:
            self._release_file_lock(fd)

    async def areserve_attempt(self, provider: str, model: str) -> str:
        """Async wrapper keeping blocking file locks off the event loop."""
        return await asyncio.to_thread(self.reserve_attempt, provider, model)

    async def asettle_attempt(
        self,
        attempt_id: str,
        *,
        usage: dict[str, Any] | None = None,
        success: bool = True,
        error: str | None = None,
        status_code: int | None = None,
    ) -> None:
        """Async wrapper keeping blocking file locks off the event loop."""
        await asyncio.to_thread(
            self.settle_attempt,
            attempt_id,
            usage=usage,
            success=success,
            error=error,
            status_code=status_code,
        )
def validate_dispatch_campaign(
    dispatch_policy: Any,
    quota_ledger: QuotaLedger | None = None,
) -> str:
    """Enforce explicit campaign identification and quota ledger when dispatch is authorized.

    Whenever a dispatch policy permits network inference (can_dispatch is True):
    1. A QuotaLedger instance is strictly required (cannot be None).
    2. The campaign_id must be non-empty and must NOT be 'default'. Silent fallback
       to unbudgeted 'default' campaigns is refused fail-closed.

    Returns the validated campaign_id.
    """
    can_dispatch = bool(getattr(
        dispatch_policy,
        "can_dispatch",
        not isinstance(dispatch_policy, BlockedLiveDispatchPolicy) if dispatch_policy is not None else False,
    ))
    if not can_dispatch:
        campaign_id = getattr(quota_ledger, "campaign_id", "") if quota_ledger is not None else ""
        return str(campaign_id or "blocked")

    if quota_ledger is None:
        raise QuotaCampaignError(
            "A configured QuotaLedger is strictly required whenever provider dispatch is authorized."
        )

    campaign_id = getattr(quota_ledger, "campaign_id", None)
    campaign_id_str = str(campaign_id or "").strip()
    if not campaign_id_str:
        raise QuotaCampaignError(
            "QUOTA_CAMPAIGN_ID is required and must be non-empty whenever provider dispatch is authorized."
        )
    if campaign_id_str.lower() == "default":
        raise QuotaCampaignError(
            "Silent fallback to campaign 'default' is refused whenever provider dispatch is authorized. "
            "An explicit, non-default QUOTA_CAMPAIGN_ID must be configured."
        )

    return campaign_id_str


# ==============================================================================
# Process-wide Shared Quota Ledger Singleton
# ==============================================================================

_process_ledger: QuotaLedger | None = None
_process_ledger_lock = threading.Lock()


def get_process_quota_ledger() -> QuotaLedger:
    global _process_ledger
    if _process_ledger is None:
        with _process_ledger_lock:
            if _process_ledger is None:
                from app.core.config import settings

                state_path = settings.QUOTA_STATE_PATH
                state_path.parent.mkdir(parents=True, exist_ok=True)
                campaign_id = getattr(settings, "QUOTA_CAMPAIGN_ID", "").strip()
                config = QuotaConfig(
                    enabled=settings.QUOTA_ENABLED,
                    campaign_id=campaign_id,
                    max_campaign_attempts=settings.QUOTA_CAMPAIGN_MAX_ATTEMPTS,
                    max_requests_per_minute=settings.QUOTA_MAX_REQUESTS_PER_MINUTE,
                    max_requests_per_day=settings.QUOTA_MAX_REQUESTS_PER_DAY,
                    max_total_attempts=settings.QUOTA_MAX_TOTAL_ATTEMPTS,
                    min_request_interval_seconds=settings.QUOTA_MIN_REQUEST_INTERVAL_SECONDS,
                    in_flight_timeout_seconds=settings.QUOTA_IN_FLIGHT_TIMEOUT_SECONDS,
                    lock_timeout_seconds=settings.QUOTA_LOCK_TIMEOUT_SECONDS,
                    state_path=state_path,
                )
                _process_ledger = QuotaLedger(config)
    return _process_ledger


def reset_process_quota_ledger() -> None:
    global _process_ledger
    with _process_ledger_lock:
        _process_ledger = None
