"""Hosted chat-completions adapter (OpenAI-compatible endpoints).

Provider selection and request/response parsing adapted from Hassan's
enterprise-knowledge-bot (commit e67771a15f49a79443a365fbce85b8559ef43fb7,
repository https://github.com/Hassan092-prog/enterprise-knowledge-bot,
`src/llm_factory.py` and `src/config.py`). That repository carries no
LICENSE file at this revision; the knowledge-bot source is owned by the
same project author. Adapted here onto KNEXUS's canonical contract,
httpx transport, typed-failure boundary, and the published shared
dispatch/quota foundation (`app.core.dispatch_policy`,
`app.core.quota.QuotaLedger`). Differences:

- No LangChain dependency: uses the existing httpx dependency only.
- No automatic retries and no provider/model fallback (the source retries
  429/5xx with backoff; that behavior is deliberately not carried over).
- No semantic cache and no query condensation: Phase 1 is non-streaming,
  single-turn, and every query must go to the provider for honest audit.
- KNEXUS canonical schema replaces `[Source: file, Page X]` prose
  citations with inline [citation_id] markers validated against
  authorized evidence.
- Dispatch is fail-closed: an explicit DispatchPolicy is checked before
  any HTTP client/socket creation, and hosted providers default to
  BlockedLiveDispatchPolicy when none is injected. Credentials, provider
  selection, and harness flags never grant authorization.
- Composed ledger lifecycle: when a QuotaLedger is supplied, the attempt
  is reserved durably before dispatch and settled on every exit path.
  Available provider usage is captured before response parsing and
  canonical validation (a successful provider response followed by
  invalid output still incurred charges). Missing or malformed usage
  stays unresolved in the ledger; it is never invented as zero.
  Settlement failures are never swallowed.
"""
import asyncio
from typing import Any

import httpx
from pydantic import ValidationError

from app.core.dispatch_policy import (
    BlockedLiveDispatchPolicy,
    DispatchPolicy,
)
from app.core.quota import QuotaLedger
from app.schemas import GenerationRequest, GenerationResult, validate_generation_result
import logging
from app.services.generation.errors import (
    GenerationSettlementError,
    MalformedOutputError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

logger = logging.getLogger("knexus.generation")

_background_cleanup_tasks: set[asyncio.Task[Any]] = set()


def _track_cleanup_task(task: asyncio.Task[Any]) -> None:
    _background_cleanup_tasks.add(task)

    def _on_done(t: asyncio.Task[Any]) -> None:
        _background_cleanup_tasks.discard(t)
        try:
            if not t.cancelled():
                exc = t.exception()
                if exc is not None:
                    logger.warning("Background cleanup task failed: %s", type(exc).__name__)
        except (asyncio.CancelledError, Exception):
            pass

    task.add_done_callback(_on_done)


async def drain_cleanup_tasks() -> None:
    """Await all active background cleanup tasks (for testing and graceful shutdown).

    Cleanup is best-effort if the event loop shuts down, with stale-reservation
    recovery in the quota ledger (governed by in_flight_timeout_seconds, default 60.0s)
    serving as the durable backstop.
    """
    if _background_cleanup_tasks:
        await asyncio.gather(*list(_background_cleanup_tasks), return_exceptions=True)

DEFAULT_ENDPOINTS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "groq": "https://api.groq.com/openai/v1",
    "mistral": "https://api.mistral.ai/v1",
}

MISTRAL_TOKEN_LIMIT_KEY = "max_tokens"
"""Mistral's documented completion-limit parameter name at the pinned source.

Groq and OpenAI document `max_completion_tokens` (Groq marks `max_tokens`
deprecated); Mistral's chat-completions API documents `max_tokens`. This
per-provider split is pinned by tests.
"""

_STRICT_SCHEMA_CACHE: dict[str, object] | None = None
"""Merged schema cache; computed once from the canonical model."""


def strict_generation_schema() -> dict[str, object]:
    """Canonical GenerationResult schema made strict-mode compliant.

    `GenerationResult.model_json_schema()` marks `abstention_reason` with a
    `default` and omits it from `required` because the field is optional in
    Pydantic. Strict json_schema providers (OpenAI, Groq) reject a `default`
    keyword and require every property in `required`; here all fields become
    required (the model must always emit the key, and the canonical
    validation below still enforces the exact answer/abstention invariants).

    Only `default` is stripped and every property is listed in `required`;
    field names, object structure, `anyOf` null-unions and all other
    canonical constraints are preserved verbatim. Undocumented strict-mode
    keywords (`minLength`, `minimum`, `maxItems`, `title`, ...) are neither
    assumed rejected nor silently removed, and no recursive filtering runs
    that could drop properties. Compatibility with any provider is
    established only by an authorized live response, never by assumption.
    """
    global _STRICT_SCHEMA_CACHE
    if _STRICT_SCHEMA_CACHE is None:
        schema = GenerationResult.model_json_schema()
        properties = {
            name: {key: value for key, value in spec.items() if key != "default"}
            for name, spec in schema["properties"].items()
        }
        _STRICT_SCHEMA_CACHE = {
            **schema,
            "properties": properties,
            "required": sorted(properties),
        }
    return _STRICT_SCHEMA_CACHE


def _rate_limit_diagnostics(response: httpx.Response) -> str:
    """Sanitized, bounded HTTP header summary for typed error messages.

    Only a few short limit/retry header values are included; provider
    response bodies are never copied into error text.
    """
    parts: list[str] = []
    for name in ("retry-after", "x-ratelimit-limit-requests", "x-ratelimit-remaining-requests"):
        value = response.headers.get(name)
        if value:
            # Bound each value; header values are provider-controlled.
            parts.append(f"{name}={str(value).strip()[:40]}")
    if not parts:
        return ""
    return " (" + "; ".join(parts[:3]) + ")"


async def hosted_generate(
    request: GenerationRequest,
    *,
    provider: str,
    system_prompt: str,
    prompt: str,
    url: str,
    model: str,
    timeout: float,
    api_key: str,
    num_predict: int,
    temperature: float = 0.0,
    seed: int | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
    dispatch_policy: DispatchPolicy | None = None,
    quota_ledger: QuotaLedger | None = None,
    reasoning_effort: str | None = None,
    include_reasoning: bool | None = None,
) -> GenerationResult:
    """Send a chat completion and parse a canonical GenerationResult.

    Authorization is checked before any HTTP client or socket is created.
    `dispatch_policy=None` defaults to BlockedLiveDispatchPolicy, so no
    hosted dispatch is possible without explicit injected authorization.
    When `quota_ledger` is supplied the attempt is reserved before dispatch
    and settled exactly once on every exit path; usage is captured from the
    response body before content parsing/validation so charges incurred by
    invalid output are still recorded. Reserve failures propagate the
    published raw ledger exceptions; settlement failures become
    GenerationSettlementError while preserving the preceding provider
    failure classification.
    """
    # 1. Authorization boundary: fail before any client/socket creation.
    #    API keys, provider selection, and --run-live flags never authorize.
    if dispatch_policy is not None:
        policy = dispatch_policy
    else:
        from app.api.dependencies import get_dispatch_policy
        policy = get_dispatch_policy()
    policy.check_dispatch(provider, model)

    # 2. Durable reserve-before-dispatch using the published ledger methods.
    attempt_id: str | None = None
    if quota_ledger is not None:
        caller_abandoned = False

        async def _do_reserve() -> str:
            aid = await quota_ledger.areserve_attempt(provider, model)
            if caller_abandoned:
                try:
                    await quota_ledger.asettle_attempt(
                        aid,
                        success=False,
                        error="CancelledError",
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to settle abandoned reservation %s: %s",
                        aid,
                        type(exc).__name__,
                    )
            return aid

        reserve_task = asyncio.create_task(_do_reserve())

        def _on_reserve_done(t: asyncio.Task[str]) -> None:
            if caller_abandoned:
                try:
                    if not t.cancelled():
                        exc = t.exception()
                        if exc is not None:
                            logger.warning(
                                "Abandoned reservation task failed: %s",
                                type(exc).__name__,
                            )
                except (asyncio.CancelledError, Exception):
                    pass

        reserve_task.add_done_callback(_on_reserve_done)

        try:
            await asyncio.shield(reserve_task)
            attempt_id = reserve_task.result()
        except asyncio.CancelledError:
            caller_abandoned = True
            if reserve_task.done():
                if not reserve_task.cancelled() and reserve_task.exception() is None:
                    aid = reserve_task.result()

                    async def _settle_cancelled(reservation_id: str) -> None:
                        try:
                            await quota_ledger.asettle_attempt(
                                reservation_id,
                                success=False,
                                error="CancelledError",
                            )
                        except Exception as exc:
                            logger.warning(
                                "Failed to settle cancelled reservation %s: %s",
                                reservation_id,
                                type(exc).__name__,
                            )

                    cleanup_task = asyncio.create_task(_settle_cancelled(aid))
                    _track_cleanup_task(cleanup_task)
            else:
                _track_cleanup_task(reserve_task)
            raise

    settled = False  # one-shot settlement guard: at most one settle per attempt

    async def settle(
        *,
        success: bool,
        error: str | None = None,
        status_code: int | None = None,
        usage: Any = None,
    ) -> None:
        nonlocal settled
        if quota_ledger is None or attempt_id is None or settled:
            return
        settled = True
        try:
            await quota_ledger.asettle_attempt(
                attempt_id,
                usage=usage,
                success=success,
                error=error,
                status_code=status_code,
            )
        except Exception as exc:
            # Never swallowed: mirror the published TokenCountingSettlementError
            # pattern; the reservation stays outstanding in the ledger.
            exc_name = type(exc).__name__
            if not success:
                detail = (
                    error or (f"http_{status_code}" if status_code else "provider_error")
                )
                msg = (
                    f"Quota settlement failed ({exc_name}); outstanding "
                    f"reservation preserved. Original provider failure: {detail}"
                )
            else:
                msg = (
                    f"Quota settlement failed ({exc_name}); outstanding "
                    "reservation preserved."
                )
            raise GenerationSettlementError(
                msg, provider_error=error, status_code=status_code
            ) from None

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": prompt},
    ]
    payload: dict[str, object] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "generation_result",
                "strict": True,
                "schema": strict_generation_schema(),
            },
        },
    }
    # Provider-aware completion limit: Groq/OpenAI document
    # `max_completion_tokens` (Groq marks `max_tokens` deprecated); Mistral
    # documents `max_tokens` at the pinned source.
    if provider == "mistral":
        payload[MISTRAL_TOKEN_LIMIT_KEY] = num_predict
    else:
        payload["max_completion_tokens"] = num_predict
    if seed is not None:
        payload["seed"] = seed
    if reasoning_effort is not None:
        payload["reasoning_effort"] = reasoning_effort
    if include_reasoning is not None:
        payload["include_reasoning"] = include_reasoning
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        async with httpx.AsyncClient(
            base_url=url, timeout=httpx.Timeout(timeout), transport=transport
        ) as client:
            response = await client.post(
                "/chat/completions", json=payload, headers=headers
            )
            response.raise_for_status()
    except asyncio.CancelledError:
        # External cancellation or overall-deadline cancellation.
        if quota_ledger is not None and attempt_id is not None and not settled:
            settled = True

            async def _settle_in_flight(reservation_id: str) -> None:
                try:
                    await quota_ledger.asettle_attempt(
                        reservation_id,
                        usage=None,
                        success=False,
                        error="cancelled",
                    )
                except Exception as exc:
                    logger.warning(
                        "Failed to settle cancelled reservation %s: %s",
                        reservation_id,
                        type(exc).__name__,
                    )

            cleanup_task = asyncio.create_task(_settle_in_flight(attempt_id))
            _track_cleanup_task(cleanup_task)
        raise
    except httpx.TimeoutException as exc:
        await settle(success=False, error="timeout")
        raise ProviderTimeoutError("Hosted provider request timed out") from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        diagnostic = (
            _rate_limit_diagnostics(exc.response)
            if status == 429
            else ""
        )
        await settle(success=False, error=f"http_{status}", status_code=status)
        message_tail = "; no retries or fallback permitted" if status == 429 else ""
        raise ProviderUnavailableError(
            f"Hosted provider returned HTTP {status}{message_tail}{diagnostic}"
        ) from exc
    except httpx.HTTPError as exc:
        await settle(success=False, error="transport_error")
        raise ProviderUnavailableError("Hosted provider request failed") from exc

    try:
        body = response.json()
    except (ValueError, TypeError) as exc:
        await settle(success=False, error="invalid_http_body")
        raise MalformedOutputError(
            "Hosted provider returned an invalid HTTP response"
        ) from exc

    # Capture usage before any content validation: a successful provider
    # response followed by invalid output still incurred charges, so the
    # ledger dollar/token record must not depend on output legality. The
    # ledger itself validates usage shape; missing usage stays unresolved,
    # never invented as zero.
    usage = body.get("usage") if isinstance(body, dict) else None
    choices = body.get("choices") if isinstance(body, dict) else None
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        await settle(success=False, error="malformed_choices", usage=usage)
        raise MalformedOutputError("Hosted provider response has no single choice")
    finish_reason = choices[0].get("finish_reason")
    message = choices[0].get("message")
    if not isinstance(message, dict) or not isinstance(message.get("content"), str):
        if isinstance(message, dict) and isinstance(message.get("reasoning"), str):
            # Reasoning-only responses (e.g. gpt-oss with include_reasoning):
            # reasoning text is never parsed as the answer.
            await settle(success=False, error="reasoning_without_content", usage=usage)
            raise MalformedOutputError(
                "Hosted provider returned reasoning without the required content"
            )
        await settle(success=False, error="missing_content", usage=usage)
        raise MalformedOutputError("Hosted provider response has no text result")
    if finish_reason == "length":
        # Truncation is deliberate: even a fragment that happens to parse is
        # not trusted as a complete canonical result.
        await settle(success=False, error="finish_reason_length", usage=usage)
        raise MalformedOutputError(
            "Hosted provider response was truncated (finish_reason 'length') "
            "before a complete generation result"
        )
    # Refusals expressed as prose content (provider-specific, undocumented
    # shapes) land here: the content is never copied into the error.
    try:
        result = GenerationResult.model_validate_json(message["content"])
    except (ValidationError, ValueError, TypeError) as exc:
        await settle(success=False, error="invalid_result_json", usage=usage)
        raise MalformedOutputError(
            "Hosted provider output was not the required JSON result"
        ) from exc
    try:
        validated = validate_generation_result(result, request)
    except (ValueError, TypeError) as exc:
        await settle(success=False, error="citation_contract_violation", usage=usage)
        raise MalformedOutputError(
            "Hosted provider output does not satisfy the generation contract"
        ) from exc
    await settle(success=True, usage=usage)
    return validated
