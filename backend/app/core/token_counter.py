"""Model-specific input token counting and validation boundary.

Enforces fail-closed token validation before embedding dispatch for hosted models.
Applies dispatch policies, explicit overhead accounting, and strict schema validation.

Limitation Note:
HTTPX timeout enforces transport/inactivity timeouts on individual network requests.
It does not serve as an overall monotonic document-validation deadline. When passed a
remaining allowance timeout, the counter limits transport blocking to the remaining
allowance. In-flight synchronous socket calls cannot be preemptively terminated mid-flight
from the caller thread; post-call monotonic deadline validation ensures any late response
is rejected fail-closed.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from typing import Any, Callable, Protocol
import httpx

from app.core.config import settings
from app.core.dispatch_policy import BlockedLiveDispatchPolicy, DispatchPolicy, LiveInferenceBlockedError
from app.core.quota import QuotaCampaignError, QuotaLedger, validate_dispatch_campaign
from app.services.ingestion.errors import TokenCountingError, TokenCountingSettlementError


@dataclass(frozen=True)
class TokenCountResult:
    """Validated token count result with separate raw and effective counts."""
    raw_tokens: int            # Direct provider-reported token count for the exact input text
    overhead_tokens: int       # Approved model-specific internal overhead (e.g. 8 tokens support guidance)
    effective_tokens: int      # raw_tokens + overhead_tokens evaluated against the ceiling
    model_name: str
    content_hash: str          # SHA-256 of the exact input string
    request_type: str          # "document" or "query"


def validate_token_count_result(
    result: TokenCountResult,
    *,
    expected_model: str,
    expected_text: str,
    expected_request_type: str,
) -> None:
    """Validate returned count result correspondence and internal consistency."""
    expected_hash = hashlib.sha256(expected_text.encode("utf-8")).hexdigest()
    if result.model_name != expected_model:
        raise TokenCountingError(
            f"Model mismatch in token count result: expected '{expected_model}', got '{result.model_name}'"
        )
    if result.content_hash != expected_hash:
        raise TokenCountingError(
            "Content hash mismatch in token count result: correspondence check failed."
        )
    if result.request_type != expected_request_type:
        raise TokenCountingError(
            f"Request type mismatch in token count result: expected '{expected_request_type}', got '{result.request_type}'"
        )
    if not isinstance(result.raw_tokens, int) or isinstance(result.raw_tokens, bool) or result.raw_tokens < 0:
        raise TokenCountingError("Token count result contains invalid raw_tokens.")
    if not isinstance(result.overhead_tokens, int) or isinstance(result.overhead_tokens, bool) or result.overhead_tokens < 0:
        raise TokenCountingError("Token count result contains invalid overhead_tokens.")
    if not isinstance(result.effective_tokens, int) or isinstance(result.effective_tokens, bool) or result.effective_tokens < 0:
        raise TokenCountingError("Token count result contains invalid effective_tokens.")
    if result.effective_tokens != result.raw_tokens + result.overhead_tokens:
        raise TokenCountingError(
            "Token count result is mathematically inconsistent: effective_tokens != raw_tokens + overhead_tokens."
        )


class TokenCounter(Protocol):
    """Contract for counting and validating input tokens."""

    def count_tokens(
        self,
        text: str,
        *,
        model: str,
        request_type: str = "document",
        timeout: float | None = None,
    ) -> TokenCountResult: ...


class GoogleGenAITokenCounter:
    """Hosted Google AI Studio token counter using models/{model}:countTokens.

    Validates inputs and extracts provider-reported totalTokens before embedding.
    Enforces fail-closed dispatch policies before HTTP client or socket creation.
    """

    def __init__(
        self,
        model_name: str | None = None,
        *,
        overhead_tokens: int = 8,
        max_allowed_tokens: int = 2048,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 10.0,
        transport: httpx.BaseTransport | None = None,
        dispatch_policy: DispatchPolicy | None = None,
        quota_ledger: QuotaLedger | None = None,
    ) -> None:
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be a finite positive number")
        self.model_name = model_name or (
            settings.EMBEDDING_MODEL_NAME
            if settings.EMBEDDING_PROVIDER == "google"
            else "gemini-embedding-001"
        )
        self.overhead_tokens = overhead_tokens
        self.max_allowed_tokens = max_allowed_tokens
        self.api_key = api_key or (
            settings.EMBEDDING_API_KEY.get_secret_value()
            if settings.EMBEDDING_API_KEY is not None
            else None
        )
        self.base_url = (
            base_url or settings.EMBEDDING_BASE_URL or "https://generativelanguage.googleapis.com"
        ).rstrip("/")
        self.timeout = float(timeout)
        self.transport = transport
        self.dispatch_policy = dispatch_policy or BlockedLiveDispatchPolicy()
        self.quota_ledger = quota_ledger
        try:
            validate_dispatch_campaign(self.dispatch_policy, self.quota_ledger)
        except QuotaCampaignError as exc:
            raise TokenCountingError(str(exc)) from exc
        self._cache: dict[tuple[str, str, str], TokenCountResult] = {}

    def _settle_attempt(
        self,
        attempt_id: str | None,
        *,
        success: bool,
        error: str | None = None,
        status_code: int | None = None,
        provider_failure_detail: str | None = None,
    ) -> None:
        """Settle attempt with the durable quota ledger.

        If settlement fails, outstanding accounting is preserved in the ledger,
        and a deliberate TokenCountingSettlementError is propagated while safely
        preserving the classification of any preceding provider failure.
        Never retries the provider request or leaks credentials/bodies.
        """
        if not self.quota_ledger or not attempt_id:
            return

        try:
            self.quota_ledger.settle_attempt(
                attempt_id,
                success=success,
                error=error,
                status_code=status_code,
                usage=None,
            )
        except Exception as exc:
            exc_name = type(exc).__name__
            if not success:
                detail = provider_failure_detail or error or (f"http_{status_code}" if status_code else "provider_error")
                msg = (
                    f"Quota settlement failed ({exc_name}); outstanding reservation preserved. "
                    f"Original provider failure: {detail}"
                )
            else:
                msg = f"Quota settlement failed ({exc_name}); outstanding reservation preserved."
            raise TokenCountingSettlementError(
                msg,
                provider_error=error,
                status_code=status_code,
            ) from None

    def count_tokens(
        self,
        text: str,
        *,
        model: str | None = None,
        request_type: str = "document",
        timeout: float | None = None,
    ) -> TokenCountResult:
        target_model = model or self.model_name
        normalized_target_model = target_model.removeprefix("models/")
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        cache_key = (normalized_target_model, request_type, content_hash)

        if cache_key in self._cache:
            return self._cache[cache_key]

        if not text:
            result = TokenCountResult(
                raw_tokens=0,
                overhead_tokens=0,
                effective_tokens=0,
                model_name=target_model,
                content_hash=content_hash,
                request_type=request_type,
            )
            self._cache[cache_key] = result
            return result

        # 1. Enforce dispatch policy: fails closed before creating client or HTTP socket
        self.dispatch_policy.check_dispatch("google", target_model)
        try:
            validate_dispatch_campaign(self.dispatch_policy, self.quota_ledger)
        except QuotaCampaignError as exc:
            raise TokenCountingError(str(exc)) from exc

        # 2. Credential validation
        if not self.api_key or not self.api_key.strip():
            raise TokenCountingError(
                "Set EMBEDDING_API_KEY for hosted token counting with provider 'google'."
            )

        # 3. Timeout validation & resolution
        if timeout is not None:
            if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
                raise ValueError("timeout must be a finite positive number")
            effective_timeout = min(self.timeout, float(timeout))
        else:
            effective_timeout = self.timeout

        # 4. Quota accounting for counting calls using real published ledger interface
        attempt_id: str | None = None
        if self.quota_ledger:
            attempt_id = self.quota_ledger.reserve_attempt("google", target_model)

        endpoint = f"{self.base_url}/v1beta/models/{normalized_target_model}:countTokens"
        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "contents": [
                {
                    "parts": [{"text": text}]
                }
            ]
        }

        settled = False
        outcome_success = False
        outcome_error: str | None = None
        outcome_status: int | None = None
        outcome_detail: str | None = None

        try:
            try:
                with httpx.Client(transport=self.transport, timeout=effective_timeout) as client:
                    response = client.post(endpoint, headers=headers, json=payload)
            except httpx.TimeoutException:
                outcome_error = "timeout"
                outcome_detail = "Google countTokens request timed out."
                raise TokenCountingError("Google countTokens request timed out.")
            except httpx.HTTPError:
                outcome_error = "network_error"
                outcome_detail = "Google countTokens network transport error."
                raise TokenCountingError("Google countTokens network transport error.")

            status_code = response.status_code
            outcome_status = status_code
            if status_code != 200:
                outcome_error = f"http_{status_code}"
                outcome_detail = f"Google countTokens failed with HTTP status {status_code}."
                raise TokenCountingError(
                    f"Google countTokens failed with HTTP status {status_code}."
                )

            try:
                data = response.json()
            except Exception:
                outcome_error = "malformed_json"
                outcome_detail = "Google countTokens returned malformed JSON payload."
                raise TokenCountingError("Google countTokens returned malformed JSON payload.")

            if not isinstance(data, dict) or "totalTokens" not in data:
                outcome_error = "missing_total_tokens"
                outcome_detail = "Google countTokens response missing 'totalTokens' field."
                raise TokenCountingError("Google countTokens response missing 'totalTokens' field.")

            raw_tokens = data["totalTokens"]
            if not isinstance(raw_tokens, int) or isinstance(raw_tokens, bool) or raw_tokens < 0:
                outcome_error = "invalid_total_tokens"
                outcome_detail = "Google countTokens returned non-integer or negative token count."
                raise TokenCountingError(
                    "Google countTokens returned non-integer or negative token count."
                )

            outcome_success = True
            effective_tokens = raw_tokens + self.overhead_tokens
            res = TokenCountResult(
                raw_tokens=raw_tokens,
                overhead_tokens=self.overhead_tokens,
                effective_tokens=effective_tokens,
                model_name=target_model,
                content_hash=content_hash,
                request_type=request_type,
            )
            self._cache[cache_key] = res
            return res
        except BaseException as exc:
            if not outcome_error and not outcome_success:
                outcome_error = type(exc).__name__
            raise
        finally:
            if attempt_id is not None and not settled:
                settled = True
                self._settle_attempt(
                    attempt_id,
                    success=outcome_success,
                    error=outcome_error,
                    status_code=outcome_status,
                    provider_failure_detail=outcome_detail,
                )


class MockTokenCounter:
    """Injected deterministic token counter for offline tests."""

    def __init__(
        self,
        *,
        model_name: str = "gemini-embedding-001",
        overhead_tokens: int = 8,
        max_allowed_tokens: int = 2048,
        token_multiplier: float = 0.25,
        fixed_count: int | None = None,
        custom_counts: dict[str, int] | None = None,
        error_to_raise: Exception | None = None,
        dispatch_policy: DispatchPolicy | None = None,
        deadline_seconds: float | None = None,
        clock: Callable[[], float] | None = None,
        time_advance_callback: Callable[[], None] | None = None,
    ) -> None:
        self.model_name = model_name
        self.overhead_tokens = overhead_tokens
        self.max_allowed_tokens = max_allowed_tokens
        self.token_multiplier = token_multiplier
        self.fixed_count = fixed_count
        self.custom_counts = custom_counts or {}
        self.error_to_raise = error_to_raise
        self.dispatch_policy = dispatch_policy
        self.deadline_seconds = deadline_seconds
        self.clock = clock
        self.time_advance_callback = time_advance_callback
        self.counted_calls: list[tuple[str, str, str]] = []
        self._cache: dict[tuple[str, str, str], TokenCountResult] = {}
        self.last_timeout: float | None = None

    def count_tokens(
        self,
        text: str,
        *,
        model: str | None = None,
        request_type: str = "document",
        timeout: float | None = None,
    ) -> TokenCountResult:
        if timeout is not None:
            if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
                raise ValueError("timeout must be a finite positive number")
        self.last_timeout = timeout

        target_model = model or self.model_name
        normalized_target_model = target_model.removeprefix("models/")
        content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        cache_key = (normalized_target_model, request_type, content_hash)
        if cache_key in self._cache:
            return self._cache[cache_key]

        if self.dispatch_policy:
            self.dispatch_policy.check_dispatch("google", target_model)

        self.counted_calls.append((text, target_model, request_type))

        if self.time_advance_callback:
            self.time_advance_callback()

        if self.error_to_raise:
            raise self.error_to_raise

        if not text:
            res = TokenCountResult(0, 0, 0, target_model, content_hash, request_type)
            self._cache[cache_key] = res
            return res

        if text in self.custom_counts:
            raw = self.custom_counts[text]
        elif self.fixed_count is not None:
            raw = self.fixed_count
        else:
            raw = max(1, int(len(text) * self.token_multiplier))

        effective = raw + self.overhead_tokens
        res = TokenCountResult(
            raw_tokens=raw,
            overhead_tokens=self.overhead_tokens,
            effective_tokens=effective,
            model_name=target_model,
            content_hash=content_hash,
            request_type=request_type,
        )
        self._cache[cache_key] = res
        return res


def get_default_token_counter(
    model_name: str | None = None,
    *,
    dispatch_policy: DispatchPolicy | None = None,
    quota_ledger: QuotaLedger | None = None,
) -> TokenCounter:
    from app.core.quota import get_process_quota_ledger

    active_ledger = quota_ledger if quota_ledger is not None else get_process_quota_ledger()
    resolved_model = model_name or (
        settings.EMBEDDING_MODEL_NAME
        if settings.EMBEDDING_PROVIDER == "google"
        else "gemini-embedding-001"
    )
    try:
        validate_dispatch_campaign(dispatch_policy, active_ledger)
    except QuotaCampaignError as exc:
        raise TokenCountingError(str(exc)) from exc
    return GoogleGenAITokenCounter(
        model_name=resolved_model,
        overhead_tokens=settings.EMBEDDING_COUNTING_OVERHEAD_TOKENS,
        max_allowed_tokens=settings.EMBEDDING_MAX_INPUT_TOKENS,
        timeout=settings.EMBEDDING_TIMEOUT,
        dispatch_policy=dispatch_policy,
        quota_ledger=active_ledger,
    )
