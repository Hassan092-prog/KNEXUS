"""Non-streaming authorized retrieval and generation endpoint."""
from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import (
    get_current_actor,
    get_generation_service,
    get_retrieval_service,
)
from app.api.errors import APIProblem
from app.core.database import get_db
from app.core.generation import GenerationService, run_generation
from app.schemas import (
    ActorContext,
    Citation,
    GenerationRequest,
    QueryMeta,
    QueryRequest,
    QueryResponse,
)
from app.services.generation.errors import (
    ContextBudgetExceededError,
    GenerationConfigurationError,
    MalformedOutputError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from app.services.ingestion.errors import EmbeddingUnavailableError
from app.services.retrieval.service import RetrievalService


router = APIRouter()


def _model_name(service: GenerationService) -> str:
    if getattr(service, "provider", None) == "fake":
        return "fake"
    return str(getattr(service, "model", "configured-provider"))


@router.post("/query", response_model=QueryResponse, summary="Query permitted document evidence")
async def query_documents(
    payload: QueryRequest,
    session: AsyncSession = Depends(get_db),
    actor: ActorContext = Depends(get_current_actor),
    retrieval: RetrievalService = Depends(get_retrieval_service),
    generator: GenerationService = Depends(get_generation_service),
) -> QueryResponse:
    retrieval_started = perf_counter()
    try:
        evidence = await retrieval.retrieve(
            session, actor, payload.question, payload.top_k
        )
    except EmbeddingUnavailableError:
        raise APIProblem(
            503, "PROVIDER_UNAVAILABLE", "The configured embedding service is unavailable."
        )
    retrieval_ms = (perf_counter() - retrieval_started) * 1000
    if not evidence:
        return QueryResponse(
            answer=None,
            citations=[],
            abstained=True,
            abstention_reason="No sufficiently relevant accessible evidence was found.",
            session_id=uuid4(),
            meta=QueryMeta(
                retrieval_time_ms=retrieval_ms,
                generation_time_ms=0.0,
                model="not_used",
            ),
        )

    generation_started = perf_counter()
    try:
        result = await run_generation(
            generator,
            GenerationRequest(question=payload.question, evidence=evidence),
        )
    except ProviderTimeoutError:
        raise APIProblem(504, "PROVIDER_UNAVAILABLE", "The generation request timed out.")
    except ProviderUnavailableError:
        raise APIProblem(503, "PROVIDER_UNAVAILABLE", "The generation provider is unavailable.")
    except (GenerationConfigurationError, ContextBudgetExceededError):
        raise APIProblem(503, "PROVIDER_UNAVAILABLE", "The generation provider cannot process this request.")
    except (MalformedOutputError, ValueError, TypeError):
        raise APIProblem(502, "INVALID_CITATIONS", "The generation result failed citation validation.")
    generation_ms = (perf_counter() - generation_started) * 1000

    by_id = {item.citation_id: item for item in evidence}
    citations = [
        Citation(
            id=identifier,
            chunk_id=by_id[identifier].chunk_id,
            document_id=by_id[identifier].document_id,
            document_title=by_id[identifier].document_title,
            chunk_index=by_id[identifier].chunk_index,
            page=by_id[identifier].page,
            excerpt=by_id[identifier].content,
            similarity_score=by_id[identifier].similarity_score,
        )
        for identifier in result.cited_ids
    ]
    return QueryResponse(
        answer=result.answer,
        citations=citations,
        abstained=result.abstained,
        abstention_reason=result.abstention_reason,
        session_id=uuid4(),
        meta=QueryMeta(
            retrieval_time_ms=retrieval_ms,
            generation_time_ms=generation_ms,
            model=_model_name(generator),
        ),
    )
