"""Persisted, explicitly retriable document-processing lifecycle."""
from __future__ import annotations

import inspect

import asyncio
from datetime import datetime, timezone
import logging
from typing import Callable
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.models import Document, DocumentChunk, Embedding, IngestionJob
from app.schemas import ActorContext
from app.core.config import settings
from app.core.token_counter import TokenCounter, get_default_token_counter
from app.services.ingestion.chunking import ChunkDraft, Tokenizer, chunk_document, load_embedding_tokenizer
from app.services.ingestion.embedding import Embedder, get_default_embedder, validate_embeddings
from app.services.ingestion.errors import EmbeddingUnavailableError, IngestionProcessingError
from app.services.ingestion.parsing import ParsedSection, parse_document_bytes
from app.services.ingestion.storage import read_upload


logger = logging.getLogger("knexus.ingestion")
SessionFactory = Callable[[], AsyncSession]
_PROCESSING_FAILURE = "Document processing failed. Correct the file or service configuration, then retry."
_INTERRUPTED_FAILURE = "Processing was interrupted. A retry may be started explicitly."


async def _latest_job(session: AsyncSession, org_id: UUID, document_id: UUID) -> IngestionJob | None:
    result = await session.execute(
        select(IngestionJob)
        .where(
            IngestionJob.org_id == org_id,
            IngestionJob.document_id == document_id,
        )
        .order_by(IngestionJob.attempt_number.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _mark_failed(
    session_factory: SessionFactory,
    document_id: UUID,
    *,
    code: str,
    message: str,
) -> None:
    try:
        async with session_factory() as session:
            document = await session.get(Document, document_id)
            if document is None:
                return
            job = await _latest_job(session, document.org_id, document.id)
            if job is None or job.status in {"complete", "failed"}:
                return
            now = datetime.now(timezone.utc)
            document.status = "failed"
            job.status = "failed"
            job.failure_code = code
            job.failure_message = message
            job.finished_at = now
            await session.commit()
    except Exception as exc:
        logger.warning(
            "Could not persist failed ingestion state for document %s (%s)",
            document_id,
            type(exc).__name__,
        )


def _embed_document_chunk_with_task_adaptation(embedder: Embedder, content: str) -> list[list[float]]:
    """Adapt the embedder task-type interface before dispatch without exception retries."""
    try:
        sig = inspect.signature(embedder.embed_texts)
        supports_task = "task_type" in sig.parameters or any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )
    except (ValueError, TypeError):
        supports_task = False

    if supports_task:
        return embedder.embed_texts([content], task_type="RETRIEVAL_DOCUMENT")
    return embedder.embed_texts([content])


async def process_document(
    document_id: UUID,
    *,
    parsed_sections: list[ParsedSection] | None = None,
    session_factory: SessionFactory | None = None,
    embedder: Embedder | None = None,
    tokenizer: Tokenizer | None = None,
    token_counter: TokenCounter | None = None,
) -> bool:
    """Process one persisted queued attempt. Errors become safe failed status."""
    sessions = session_factory or AsyncSessionLocal
    active_embedder = embedder or get_default_embedder()
    try:
        async with sessions() as session:
            document = await session.get(Document, document_id)
            if document is None or document.is_deleted:
                return False
            job = await _latest_job(session, document.org_id, document.id)
            if job is None or job.status != "queued" or document.status != "queued":
                return False
            now = datetime.now(timezone.utc)
            document.status = "processing"
            job.status = "processing"
            job.started_at = now
            await session.commit()

            if parsed_sections is None:
                raw = await asyncio.to_thread(read_upload, document.storage_key or "")
                sections = await asyncio.to_thread(
                    parse_document_bytes, raw, document.source_type
                )
            else:
                sections = parsed_sections
            model_limit_loader = getattr(active_embedder, "get_max_input_tokens", None)
            model_max_input_tokens = None
            if callable(model_limit_loader):
                model_max_input_tokens = await asyncio.to_thread(model_limit_loader)
            if token_counter is not None:
                chunks: list[ChunkDraft] = await asyncio.to_thread(
                    chunk_document,
                    document.id,
                    sections,
                    token_counter=token_counter,
                )
            elif tokenizer is not None:
                chunks: list[ChunkDraft] = await asyncio.to_thread(
                    chunk_document,
                    document.id,
                    sections,
                    tokenizer,
                    model_max_input_tokens=model_max_input_tokens,
                )
            elif (
                settings.EMBEDDING_PROVIDER == "google"
                or getattr(active_embedder, "model_name", "") in {"gemini-embedding-001", "text-embedding-004"}
            ):
                active_counter = get_default_token_counter(
                    getattr(active_embedder, "model_name", None),
                    dispatch_policy=getattr(active_embedder, "dispatch_policy", None),
                    quota_ledger=getattr(active_embedder, "quota_ledger", None),
                )
                chunks: list[ChunkDraft] = await asyncio.to_thread(
                    chunk_document,
                    document.id,
                    sections,
                    token_counter=active_counter,
                )
            else:
                active_tokenizer = await asyncio.to_thread(
                    load_embedding_tokenizer,
                    active_embedder.model_name,
                    active_embedder.model_revision,
                )
                chunks: list[ChunkDraft] = await asyncio.to_thread(
                    chunk_document,
                    document.id,
                    sections,
                    active_tokenizer,
                    model_max_input_tokens=model_max_input_tokens,
                )
            if not chunks:
                raise IngestionProcessingError("The document produced no searchable chunks.")

            job.total_chunks = len(chunks)
            job.chunks_processed = 0
            document.chunk_count = 0
            await session.commit()

            for chunk in chunks:
                vector_batch = await asyncio.to_thread(
                    _embed_document_chunk_with_task_adaptation, active_embedder, chunk.content
                )
                vector = validate_embeddings(vector_batch, 1)[0]
                row = DocumentChunk(
                    id=chunk.id,
                    org_id=document.org_id,
                    document_id=document.id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    page=chunk.page,
                    token_count=chunk.token_count,
                    source_metadata=chunk.source_metadata,
                )
                session.add(row)
                await session.flush()
                session.add(
                    Embedding(
                        org_id=document.org_id,
                        document_id=document.id,
                        chunk_id=chunk.id,
                        embedding=vector,
                        model_name=active_embedder.model_name,
                        model_revision=active_embedder.model_revision,
                        is_active=True,
                    )
                )
                await session.flush()
                job.chunks_processed = chunk.chunk_index + 1
                document.chunk_count = job.chunks_processed
                await session.commit()

            now = datetime.now(timezone.utc)
            document.status = "complete"
            job.status = "complete"
            job.finished_at = now
            job.failure_code = None
            job.failure_message = None
            await session.commit()
            return True
    except asyncio.CancelledError:
        await _mark_failed(
            sessions, document_id, code="INTERRUPTED", message=_INTERRUPTED_FAILURE
        )
        raise
    except Exception as exc:
        await _mark_failed(
            sessions, document_id, code="PROCESSING_FAILED", message=_PROCESSING_FAILURE
        )
        logger.warning(
            "Document ingestion failed for %s (%s)", document_id, type(exc).__name__
        )
        return False


async def recover_interrupted_jobs(
    session_factory: SessionFactory | None = None,
    *,
    workers_stopped: bool = False,
) -> int:
    """Fail abandoned jobs only after the operator confirms all workers stopped.

    The caller must establish that the service process has restarted and no worker
    can still own these jobs. This helper is deliberately never run at startup,
    because queued jobs may belong to active workers.
    """
    if not workers_stopped:
        raise ValueError("Confirm that all ingestion workers are stopped before recovery")
    sessions = session_factory or AsyncSessionLocal
    count = 0
    async with sessions() as session:
        result = await session.execute(
            select(IngestionJob).where(
                IngestionJob.status.in_(("queued", "processing"))
            )
        )
        jobs = result.scalars().all()
        now = datetime.now(timezone.utc)
        for job in jobs:
            document = await session.get(Document, job.document_id)
            job.status = "failed"
            job.failure_code = "INTERRUPTED"
            job.failure_message = _INTERRUPTED_FAILURE
            job.finished_at = now
            if document is not None and document.org_id == job.org_id:
                document.status = "failed"
            count += 1
        await session.commit()
    return count

async def enqueue_document_retry(
    session: AsyncSession, actor: ActorContext, document_id: UUID
) -> IngestionJob:
    """Explicit internal retry helper; no public retry route is contracted yet."""
    document = await session.get(Document, document_id)
    if document is None or document.org_id != actor.org_id or document.is_deleted:
        raise LookupError("Document not found")
    if document.uploaded_by != actor.user_id and "orgadmin" not in actor.effective_roles:
        raise PermissionError("Document retry is not permitted")
    latest = await _latest_job(session, document.org_id, document.id)
    if latest is None or latest.status != "failed" or document.status != "failed":
        raise ValueError("Only a failed document can be retried")
    await session.execute(
        delete(Embedding).where(
            Embedding.org_id == document.org_id,
            Embedding.document_id == document.id,
        )
    )
    await session.execute(
        delete(DocumentChunk).where(
            DocumentChunk.org_id == document.org_id,
            DocumentChunk.document_id == document.id,
        )
    )
    document.status = "queued"
    document.chunk_count = 0
    retry = IngestionJob(
        org_id=document.org_id,
        document_id=document.id,
        attempt_number=latest.attempt_number + 1,
        status="queued",
        chunks_processed=0,
        total_chunks=None,
    )
    session.add(retry)
    await session.flush()
    await session.commit()
    return retry
