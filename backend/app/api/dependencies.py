"""Server-owned dependencies shared by Phase 1 API routes."""
from __future__ import annotations

from functools import lru_cache
from typing import Any

import httpx
from fastapi import Depends, Request
from fastapi.params import Depends as DependsSentinel

from app.api.errors import APIProblem
from app.core.config import settings
from app.core.database import get_db
from app.core.demo_identity import build_demo_actor
from app.core.dispatch_policy import BlockedLiveDispatchPolicy, DispatchPolicy, MockDispatchPolicy, ServerApprovedLiveDispatchPolicy
from app.core.generation import GenerationService
from app.core.quota import QuotaCampaignError, QuotaError, QuotaLedger, get_process_quota_ledger, validate_dispatch_campaign
from app.core.token_counter import TokenCounter, get_default_token_counter
from app.schemas import ActorContext
from app.services.generation.errors import GenerationConfigurationError
from app.services.generation.generator import GenerationService as ConfiguredGenerationService
from app.services.ingestion.embedding import Embedder, get_default_embedder
from app.services.retrieval.service import RetrievalService


_IDENTITY_FIELDS = {
    "org_id", "organization_id", "user_id", "role", "effective_roles", "actor",
    "x-org-id", "x-organization-id", "x-user-id", "x-role",
    "x-effective-roles", "x-actor",
}


def get_current_actor(request: Request) -> ActorContext:
    """Phase 1 identity is fixed on the server; this is not authentication."""
    supplied = set(request.query_params.keys())
    supplied.update(name.lower().replace("_", "-") for name in request.headers.keys())
    if _IDENTITY_FIELDS.intersection(supplied):
        raise APIProblem(
            422,
            "VALIDATION_ERROR",
            "Caller-supplied identity is not accepted.",
        )
    return build_demo_actor(settings.DEMO_ACTOR_ROLE)


def get_dispatch_policy() -> DispatchPolicy:
    """Return the server-owned dispatch authorization policy (fail-closed by default)."""
    if settings.LIVE_DISPATCH_ENABLED and bool((settings.QUOTA_CAMPAIGN_ID or "").strip()):
        return ServerApprovedLiveDispatchPolicy()
    return BlockedLiveDispatchPolicy()


def get_generation_quota_ledger() -> QuotaLedger | None:
    """Return runtime quota ledger. Resolves to the shared process-wide ledger built from Settings."""
    return get_process_quota_ledger()


def get_generation_transport() -> httpx.AsyncBaseTransport | None:
    """Return runtime HTTP transport for generation; None uses default network client."""
    return None


def get_embedding_transport() -> httpx.BaseTransport | None:
    """Return runtime HTTP transport for embeddings; None uses default network client."""
    return None


def get_embedder(
    dispatch_policy: DispatchPolicy = Depends(get_dispatch_policy),
    quota_ledger: QuotaLedger | None = Depends(get_generation_quota_ledger),
    transport: httpx.BaseTransport | None = Depends(get_embedding_transport),
) -> Embedder:
    resolved_policy: DispatchPolicy = (
        get_dispatch_policy()
        if isinstance(dispatch_policy, DependsSentinel)
        else dispatch_policy
    )
    resolved_ledger: QuotaLedger | None = (
        get_generation_quota_ledger()
        if isinstance(quota_ledger, DependsSentinel)
        else quota_ledger
    )
    resolved_transport: httpx.BaseTransport | None = (
        get_embedding_transport()
        if isinstance(transport, DependsSentinel)
        else transport
    )
    return get_default_embedder(
        provider=settings.EMBEDDING_PROVIDER,
        model_name=settings.EMBEDDING_MODEL_NAME,
        revision=settings.EMBEDDING_MODEL_REVISION,
        transport=resolved_transport,
        dispatch_policy=resolved_policy,
        quota_ledger=resolved_ledger,
    )


def get_token_counter(
    dispatch_policy: DispatchPolicy = Depends(get_dispatch_policy),
    quota_ledger: QuotaLedger | None = Depends(get_generation_quota_ledger),
    transport: httpx.BaseTransport | None = Depends(get_embedding_transport),
) -> TokenCounter | None:
    resolved_policy: DispatchPolicy = (
        get_dispatch_policy()
        if isinstance(dispatch_policy, DependsSentinel)
        else dispatch_policy
    )
    resolved_ledger: QuotaLedger | None = (
        get_generation_quota_ledger()
        if isinstance(quota_ledger, DependsSentinel)
        else quota_ledger
    )
    resolved_transport: httpx.BaseTransport | None = (
        get_embedding_transport()
        if isinstance(transport, DependsSentinel)
        else transport
    )
    if settings.EMBEDDING_PROVIDER == "google":
        return get_default_token_counter(
            model_name=settings.EMBEDDING_MODEL_NAME,
            transport=resolved_transport,
            dispatch_policy=resolved_policy,
            quota_ledger=resolved_ledger,
        )
    return None


def get_retrieval_service(
    embedder: Embedder = Depends(get_embedder),
    token_counter: TokenCounter | None = Depends(get_token_counter),
) -> RetrievalService:
    """Dependency override point for offline tests; production uses configured embedder and counter."""
    resolved_embedder = (
        get_embedder()
        if isinstance(embedder, DependsSentinel)
        else embedder
    )
    resolved_token_counter = (
        get_token_counter()
        if isinstance(token_counter, DependsSentinel)
        else token_counter
    )
    return RetrievalService(embedder=resolved_embedder, token_counter=resolved_token_counter)


class _UnconfiguredGenerationService:
    """Delay provider configuration failure until a valid query uses generation."""

    provider = None
    model = "not_configured"

    async def generate(self, request):
        raise GenerationConfigurationError(
            "Set GENERATION_PROVIDER explicitly to one of: "
            "fake, groq, openai, mistral. Local Ollama provider is refused."
        )


def get_generation_service(
    dispatch_policy: DispatchPolicy = Depends(get_dispatch_policy),
    quota_ledger: QuotaLedger | None = Depends(get_generation_quota_ledger),
    transport: httpx.AsyncBaseTransport | None = Depends(get_generation_transport),
) -> GenerationService:
    """Explicit configured provider; missing configuration fails closed at query.

    Instantiates a configured service using the active dispatch policy and quota ledger.
    Cached service instances are avoided so test overrides and policy changes are never
    leaked across requests or test runs. Direct Python calls without arguments resolve
    the default policy/ledger cleanly without receiving raw FastAPI Depends sentinels.
    """
    resolved_policy: DispatchPolicy = (
        get_dispatch_policy()
        if isinstance(dispatch_policy, DependsSentinel)
        else dispatch_policy
    )
    resolved_ledger: QuotaLedger | None = (
        get_generation_quota_ledger()
        if isinstance(quota_ledger, DependsSentinel)
        else quota_ledger
    )
    resolved_transport: httpx.AsyncBaseTransport | None = (
        get_generation_transport()
        if isinstance(transport, DependsSentinel)
        else transport
    )

    # Capability-based guard (F1):
    # Any policy where can_dispatch is True strictly requires an explicit QuotaLedger.
    # No transport exemption exists: injected transports (including AsyncHTTPTransport)
    # still require an explicit ledger so live or mock dispatch is never unmetered.
    can_dispatch = getattr(
        resolved_policy, "can_dispatch", not isinstance(resolved_policy, BlockedLiveDispatchPolicy)
    )
    if can_dispatch:
        try:
            validate_dispatch_campaign(resolved_policy, resolved_ledger)
        except (QuotaCampaignError, QuotaError, ValueError) as exc:
            raise GenerationConfigurationError(str(exc)) from exc

    provider = settings.GENERATION_PROVIDER or settings.OLLAMA_PROVIDER
    if not provider:
        return _UnconfiguredGenerationService()
    provider_clean = provider.strip().lower()
    if provider_clean == "ollama":
        raise GenerationConfigurationError(
            "Local Ollama provider is deprecated and refused. KNEXUS Phase 1 uses hosted providers only."
        )
    try:
        if provider_clean in {"openai", "groq", "mistral"}:
            api_key = (
                settings.GENERATION_API_KEY.get_secret_value()
                if settings.GENERATION_API_KEY is not None
                else None
            )
            return ConfiguredGenerationService(
                provider=provider_clean,
                url=settings.GENERATION_BASE_URL,
                model=settings.GENERATION_MODEL,
                timeout=settings.GENERATION_TIMEOUT,
                num_predict=settings.GENERATION_MAX_TOKENS,
                max_prompt_chars=settings.GENERATION_MAX_PROMPT_CHARS,
                api_key=api_key,
                api_base_url=settings.GENERATION_BASE_URL,
                temperature=settings.GENERATION_TEMPERATURE,
                seed=settings.GENERATION_SEED,
                dispatch_policy=resolved_policy,
                quota_ledger=resolved_ledger,
                transport=resolved_transport,
            )
        elif provider_clean == "fake":
            return ConfiguredGenerationService(
                provider="fake",
                model="mock",
                dispatch_policy=resolved_policy,
                quota_ledger=resolved_ledger,
                transport=resolved_transport,
            )
        else:
            raise GenerationConfigurationError(
                f"Unsupported generation provider {provider!r}. "
                "Must be one of: fake, groq, openai, mistral"
            )
    except GenerationConfigurationError:
        raise
