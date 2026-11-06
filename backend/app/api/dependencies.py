"""Server-owned dependencies shared by Phase 1 API routes."""
from __future__ import annotations

from functools import lru_cache

from fastapi import Depends, Request

from app.api.errors import APIProblem
from app.core.config import settings
from app.core.database import get_db
from app.core.demo_identity import build_demo_actor
from app.core.generation import GenerationService
from app.schemas import ActorContext
from app.services.generation.errors import GenerationConfigurationError
from app.services.generation.generator import GenerationService as ConfiguredGenerationService
from app.core.token_counter import TokenCounter, get_default_token_counter
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
    return build_demo_actor()


def get_embedder() -> Embedder:
    return get_default_embedder(
        provider=settings.EMBEDDING_PROVIDER,
        model_name=settings.EMBEDDING_MODEL_NAME,
        revision=settings.EMBEDDING_MODEL_REVISION,
    )


def get_token_counter() -> TokenCounter | None:
    if settings.EMBEDDING_PROVIDER == "google":
        return get_default_token_counter(model_name=settings.EMBEDDING_MODEL_NAME)
    return None


def get_retrieval_service(
    embedder: Embedder = Depends(get_embedder),
    token_counter: TokenCounter | None = Depends(get_token_counter),
) -> RetrievalService:
    """Dependency override point for offline tests; production uses configured embedder and counter."""
    return RetrievalService(embedder=embedder, token_counter=token_counter)


class _UnconfiguredGenerationService:
    """Delay provider configuration failure until a valid query uses generation."""

    provider = None
    model = "not_configured"

    async def generate(self, request):
        raise GenerationConfigurationError(
            "Set GENERATION_PROVIDER or OLLAMA_PROVIDER explicitly to one of: "
            "fake, groq, openai, mistral, ollama"
        )


@lru_cache(maxsize=1)
def _configured_generation_service() -> GenerationService:
    provider = settings.GENERATION_PROVIDER or settings.OLLAMA_PROVIDER
    if not provider:
        return _UnconfiguredGenerationService()
    try:
        if provider in {"openai", "groq", "mistral"}:
            api_key = (
                settings.GENERATION_API_KEY.get_secret_value()
                if settings.GENERATION_API_KEY is not None
                else None
            )
            return ConfiguredGenerationService(
                provider=provider,
                url=settings.GENERATION_BASE_URL,
                model=settings.GENERATION_MODEL,
                timeout=settings.GENERATION_TIMEOUT,
                num_predict=settings.GENERATION_MAX_TOKENS,
                max_prompt_chars=settings.GENERATION_MAX_PROMPT_CHARS,
                api_key=api_key,
                api_base_url=settings.GENERATION_BASE_URL,
                temperature=settings.GENERATION_TEMPERATURE,
                seed=settings.GENERATION_SEED,
            )
        else:
            return ConfiguredGenerationService(
                provider=provider,
                url=settings.OLLAMA_BASE_URL,
                model=settings.OLLAMA_MODEL,
                timeout=settings.OLLAMA_TIMEOUT,
                num_ctx=settings.OLLAMA_NUM_CTX,
                num_predict=settings.OLLAMA_NUM_PREDICT,
                max_prompt_chars=settings.GENERATION_MAX_PROMPT_CHARS,
            )
    except GenerationConfigurationError:
        return _UnconfiguredGenerationService()


def get_generation_service() -> GenerationService:
    """Explicit configured provider; missing configuration fails closed at query."""
    return _configured_generation_service()
