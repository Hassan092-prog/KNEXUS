"""Canonical document upload, list, detail and processing-status routes."""
from __future__ import annotations

import asyncio
from pathlib import PurePath, PureWindowsPath
from typing import Callable
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, Query, Request, UploadFile
from pydantic import ValidationError
from sqlalchemy import Text, func, select
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_actor
from app.api.errors import APIProblem
from app.core.config import settings
from app.core.database import get_db
from app.models import Document, IngestionJob
from app.schemas import (
    ActorContext,
    DocumentDetail,
    DocumentList,
    DocumentStatus,
    DocumentSummary,
    PageMeta,
    UploadAccepted,
    UploadMetadata,
)
from app.services.ingestion.errors import DocumentInputError, StorageError
from app.services.ingestion.parsing import ParsedSection, parse_uploaded_document
from app.services.ingestion.processor import process_document
from app.services.ingestion.storage import delete_upload, make_storage_key, write_upload


router = APIRouter()


def _visible_document_predicate(actor: ActorContext):
    return (
        Document.org_id == actor.org_id,
        Document.is_deleted.is_(False),
        Document.allowed_roles.has_any(array(actor.effective_roles, type_=Text())),
    )


def _summary(document: Document) -> DocumentSummary:
    return DocumentSummary(
        id=document.id,
        title=document.title,
        source_type=document.source_type,
        status=document.status,
        allowed_roles=document.allowed_roles,
        chunk_count=document.chunk_count,
        created_at=document.created_at,
    )


def _detail(document: Document) -> DocumentDetail:
    return DocumentDetail(
        **_summary(document).model_dump(),
        description=document.description,
        metadata=document.metadata_json or {},
    )


def _ensure_form_has_no_identity_or_unknown_fields(request: Request, form) -> None:
    allowed = {"file", "title", "description", "allowed_roles"}
    if set(form.keys()) - allowed:
        raise APIProblem(
            422,
            "VALIDATION_ERROR",
            "The upload form contains unsupported fields.",
        )
    identity_fields = {"org_id", "user_id", "role", "effective_roles", "actor"}
    if identity_fields.intersection(request.query_params.keys()):
        raise APIProblem(
            422,
            "VALIDATION_ERROR",
            "Caller-supplied identity is not accepted.",
        )


@router.post(
    "/documents/upload",
    response_model=UploadAccepted,
    status_code=202,
    summary="Upload one PDF or DOCX document",
)
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    allowed_roles: list[str] = Form(...),
    title: str | None = Form(default=None),
    description: str | None = Form(default=None),
    session: AsyncSession = Depends(get_db),
    actor: ActorContext = Depends(get_current_actor),
) -> UploadAccepted:
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > settings.MAX_UPLOAD_BYTES + 1024 * 64:
                raise APIProblem(413, "FILE_TOO_LARGE", "The upload exceeds 10 MiB.")
        except ValueError:
            raise APIProblem(422, "VALIDATION_ERROR", "The request length is invalid.")

    form = await request.form()
    _ensure_form_has_no_identity_or_unknown_fields(request, form)
    if len(form.getlist("file")) != 1:
        raise APIProblem(422, "VALIDATION_ERROR", "Upload exactly one file.")
    if len(form.getlist("title")) > 1 or len(form.getlist("description")) > 1:
        raise APIProblem(422, "VALIDATION_ERROR", "Title and description may appear once.")

    raw = await file.read(settings.MAX_UPLOAD_BYTES + 1)
    if len(raw) > settings.MAX_UPLOAD_BYTES:
        raise APIProblem(413, "FILE_TOO_LARGE", "The upload exceeds 10 MiB.")
    filename = file.filename or ""
    safe_filename = PurePath(filename.replace("\\", "/")).name
    safe_filename = PureWindowsPath(safe_filename).name
    if not safe_filename or len(safe_filename) > 512:
        raise APIProblem(400, "INVALID_FILE", "The file name is invalid.")

    try:
        metadata = UploadMetadata.model_validate(
            {
                "title": title,
                "description": description,
                "allowed_roles": allowed_roles,
            }
        )
        source_type, parsed_sections = await asyncio.to_thread(
            parse_uploaded_document,
            safe_filename,
            file.content_type,
            raw,
        )
    except ValidationError:
        raise APIProblem(
            422, "VALIDATION_ERROR", "Upload metadata does not match the API contract."
        )
    except DocumentInputError as exc:
        detail = str(exc)
        if "10 MiB" in detail or "upload limit" in detail:
            raise APIProblem(413, "FILE_TOO_LARGE", "The upload exceeds 10 MiB.")
        raise APIProblem(400, "INVALID_FILE", detail)

    storage_key = make_storage_key(source_type)
    try:
        await asyncio.to_thread(write_upload, storage_key, raw)
    except StorageError:
        raise APIProblem(500, "INTERNAL_ERROR", "Private upload storage is unavailable.")

    document_id = uuid4()
    task_id = uuid4()
    title_value = metadata.title or PurePath(safe_filename).stem or "Uploaded document"
    document = Document(
        id=document_id,
        org_id=actor.org_id,
        uploaded_by=actor.user_id,
        title=title_value,
        source_type=source_type,
        original_filename=safe_filename,
        storage_key=storage_key,
        file_size_bytes=len(raw),
        allowed_roles=list(metadata.allowed_roles),
        status="queued",
        chunk_count=0,
        description=metadata.description,
        metadata_json={},
        is_deleted=False,
    )
    job = IngestionJob(
        id=task_id,
        org_id=actor.org_id,
        document_id=document_id,
        attempt_number=1,
        status="queued",
        chunks_processed=0,
        total_chunks=None,
    )
    try:
        session.add(document)
        await session.flush()
        session.add(job)
        await session.flush()
        await session.commit()
    except Exception:
        await session.rollback()
        await asyncio.to_thread(delete_upload, storage_key)
        raise APIProblem(500, "INTERNAL_ERROR", "The upload could not be accepted.")

    background_tasks.add_task(
        process_document, document_id, parsed_sections=parsed_sections
    )
    await file.close()
    return UploadAccepted(
        document_id=document_id,
        task_id=task_id,
        status="queued",
        message="Upload accepted for processing.",
    )


@router.get("/documents", response_model=DocumentList, summary="List accessible documents")
async def list_documents(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
    actor: ActorContext = Depends(get_current_actor),
) -> DocumentList:
    filters = _visible_document_predicate(actor)
    total = await session.scalar(
        select(func.count()).select_from(Document).where(*filters)
    )
    rows = await session.execute(
        select(Document)
        .where(*filters)
        .order_by(Document.created_at.desc(), Document.id.asc())
        .limit(limit)
        .offset(offset)
    )
    documents = rows.scalars().all()
    return DocumentList(
        data=[_summary(document) for document in documents],
        meta=PageMeta(total=int(total or 0), limit=limit, offset=offset),
    )


async def _get_document_for_actor(
    session: AsyncSession, actor: ActorContext, document_id: UUID
) -> Document:
    document = await session.get(Document, document_id)
    if document is None or document.org_id != actor.org_id or document.is_deleted:
        raise APIProblem(404, "NOT_FOUND", "The requested document was not found.")
    if not set(document.allowed_roles).intersection(actor.effective_roles):
        raise APIProblem(403, "FORBIDDEN", "This document is not available to this role.")
    return document


@router.get(
    "/documents/{document_id}",
    response_model=DocumentDetail,
    summary="Get an accessible document",
)
async def get_document(
    document_id: UUID,
    session: AsyncSession = Depends(get_db),
    actor: ActorContext = Depends(get_current_actor),
) -> DocumentDetail:
    document = await _get_document_for_actor(session, actor, document_id)
    return _detail(document)


@router.get(
    "/documents/{document_id}/status",
    response_model=DocumentStatus,
    summary="Get persisted processing status",
)
async def get_document_status(
    document_id: UUID,
    session: AsyncSession = Depends(get_db),
    actor: ActorContext = Depends(get_current_actor),
) -> DocumentStatus:
    document = await _get_document_for_actor(session, actor, document_id)
    if document.uploaded_by != actor.user_id and "orgadmin" not in actor.effective_roles:
        raise APIProblem(403, "FORBIDDEN", "Document status is not available to this actor.")
    result = await session.execute(
        select(IngestionJob)
        .where(
            IngestionJob.org_id == actor.org_id,
            IngestionJob.document_id == document.id,
        )
        .order_by(IngestionJob.attempt_number.desc())
        .limit(1)
    )
    job = result.scalar_one_or_none()
    if job is None:
        raise APIProblem(500, "INTERNAL_ERROR", "Persisted processing status is unavailable.")
    progress = None
    if job.status == "complete":
        progress = 100
    elif job.total_chunks is not None and job.total_chunks > 0:
        progress = min(99, int(job.chunks_processed * 100 / job.total_chunks))
    elif job.status == "processing":
        progress = 0
    return DocumentStatus(
        document_id=document.id,
        status=job.status,
        chunks_processed=job.chunks_processed,
        total_chunks=job.total_chunks,
        progress_percent=progress,
        failure_code=job.failure_code,
        failure_message=job.failure_message,
    )
