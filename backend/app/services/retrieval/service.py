"""PostgreSQL pgvector retrieval with authorization filters before ranking."""
from __future__ import annotations

import inspect

import asyncio
import math
from typing import Sequence

from sqlalchemy import Text, select
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import canonicalize_embedding_model_name, settings
from app.models import Document, DocumentChunk, Embedding, VECTOR_DIMENSIONS
from app.schemas import ActorContext, EvidenceChunk
from app.core.token_counter import TokenCounter, get_default_token_counter, validate_token_count_result
from app.services.ingestion.embedding import Embedder, get_default_embedder, validate_embeddings
from app.services.ingestion.errors import InputTokenLimitExceededError


def build_authorized_statement(
    actor: ActorContext,
    model_name: str,
    model_revision: str,
    query_vector: Sequence[float],
    limit: int,
):
    """Keep every tenant, current-role, lifecycle and model predicate in SQL."""
    if len(query_vector) != VECTOR_DIMENSIONS:
        raise ValueError("Query embedding must contain exactly 384 dimensions")
    distance = Embedding.embedding.cosine_distance(list(query_vector))
    similarity = (1.0 - distance).label("similarity")
    canonical_model = canonicalize_embedding_model_name(model_name)
    return (
        select(Embedding, DocumentChunk, Document, similarity)
        .join(
            DocumentChunk,
            (DocumentChunk.org_id == Embedding.org_id)
            & (DocumentChunk.document_id == Embedding.document_id)
            & (DocumentChunk.id == Embedding.chunk_id),
        )
        .join(
            Document,
            (Document.org_id == DocumentChunk.org_id)
            & (Document.id == DocumentChunk.document_id),
        )
        .where(
            Embedding.org_id == actor.org_id,
            Document.org_id == actor.org_id,
            Document.allowed_roles.has_any(array(actor.effective_roles, type_=Text())),
            Document.status == "complete",
            Document.is_deleted.is_(False),
            Embedding.is_active.is_(True),
            Embedding.model_name == canonical_model,
            Embedding.model_revision == model_revision,
        )
        .order_by(distance.asc(), DocumentChunk.id.asc())
        .limit(limit)
    )


def _embed_query_with_task_adaptation(embedder: Embedder, question: str) -> list[list[float]]:
    """Adapt the embedder task-type interface before dispatch without exception retries."""
    try:
        sig = inspect.signature(embedder.embed_texts)
        supports_task = "task_type" in sig.parameters or any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )
    except (ValueError, TypeError):
        supports_task = False

    if supports_task:
        return embedder.embed_texts([question], task_type="RETRIEVAL_QUERY")
    return embedder.embed_texts([question])


class RetrievalService:
    def __init__(
        self,
        embedder: Embedder | None = None,
        *,
        token_counter: TokenCounter | None = None,
        minimum_similarity: float | None = None,
        max_query_tokens: int | None = None,
    ) -> None:
        self.embedder = embedder or get_default_embedder()
        if token_counter is not None:
            self.token_counter = token_counter
        elif settings.EMBEDDING_PROVIDER == "google":
            self.token_counter = get_default_token_counter(
                getattr(self.embedder, "model_name", settings.EMBEDDING_MODEL_NAME),
                dispatch_policy=getattr(self.embedder, "dispatch_policy", None),
            )
        else:
            self.token_counter = None

        self.minimum_similarity = (
            settings.RETRIEVAL_MIN_SIMILARITY
            if minimum_similarity is None
            else minimum_similarity
        )
        self.max_query_tokens = (
            max_query_tokens
            if max_query_tokens is not None
            else settings.EMBEDDING_MAX_INPUT_TOKENS
        )
        if not math.isfinite(self.minimum_similarity) or not -1 <= self.minimum_similarity <= 1:
            raise ValueError("Retrieval threshold must be finite and between -1 and 1")

    async def retrieve(
        self,
        session: AsyncSession,
        actor: ActorContext,
        question: str,
        top_k: int,
    ) -> list[EvidenceChunk]:
        if self.token_counter is not None:
            count_res = await asyncio.to_thread(
                self.token_counter.count_tokens,
                question,
                model=self.embedder.model_name,
                request_type="query",
            )
            validate_token_count_result(
                count_res,
                expected_model=self.embedder.model_name,
                expected_text=question,
                expected_request_type="query",
            )
            if count_res.effective_tokens > self.max_query_tokens:
                raise InputTokenLimitExceededError(
                    f"Query token count ({count_res.effective_tokens}) exceeds maximum allowed limit ({self.max_query_tokens})"
                )
        query_vector = validate_embeddings(
            await asyncio.to_thread(_embed_query_with_task_adaptation, self.embedder, question), 1
        )[0]
        statement = build_authorized_statement(
            actor,
            self.embedder.model_name,
            self.embedder.model_revision,
            query_vector,
            top_k,
        )
        result = await session.execute(statement)
        rows = result.all()
        evidence: list[EvidenceChunk] = []
        seen_chunks = set()
        for embedding, chunk, document, score in rows:
            # Defense in depth; SQL still applies these filters before top-k ranking.
            if (
                embedding.org_id != actor.org_id
                or document.org_id != actor.org_id
                or document.status != "complete"
                or document.is_deleted
                or not set(document.allowed_roles).intersection(actor.effective_roles)
                or not embedding.is_active
                or canonicalize_embedding_model_name(embedding.model_name) != canonicalize_embedding_model_name(self.embedder.model_name)
                or embedding.model_revision != self.embedder.model_revision
                or chunk.id in seen_chunks
            ):
                continue
            similarity = float(score)
            if not math.isfinite(similarity):
                continue
            similarity = max(-1.0, min(1.0, similarity))
            if similarity < self.minimum_similarity:
                continue
            seen_chunks.add(chunk.id)
            evidence.append(
                EvidenceChunk(
                    citation_id=len(evidence) + 1,
                    chunk_id=chunk.id,
                    document_id=document.id,
                    document_title=document.title,
                    chunk_index=chunk.chunk_index,
                    page=chunk.page,
                    content=chunk.content,
                    similarity_score=similarity,
                )
            )
        return evidence
