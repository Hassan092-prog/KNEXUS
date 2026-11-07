"""Phase 1 contract references. These models do not register application routes."""
import re
from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AwareDatetime, BaseModel, ConfigDict, Field, JsonValue,
    StringConstraints, field_validator, model_validator,
)

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]
Role = Literal["employee", "manager", "orgadmin", "superadmin"]
DocumentState = Literal["queued", "processing", "complete", "failed"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ActorContext(Contract):
    """Server-owned identity, never accepted as query/upload JSON from a client."""
    user_id: UUID
    org_id: UUID
    effective_roles: list[Role] = Field(min_length=1)


class QueryRequest(Contract):
    question: Text = Field(max_length=4000)
    top_k: int = Field(default=5, ge=1, le=20, strict=True)
    stream: bool = Field(default=False, strict=True)

    @model_validator(mode="after")
    def non_streaming_only(self) -> Self:
        if self.stream:
            raise ValueError("Phase 1 baseline accepts stream=false only")
        return self


class UploadMetadata(Contract):
    title: Text | None = Field(default=None, max_length=512)
    allowed_roles: list[Role] = Field(min_length=1)
    description: Text | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def unique_roles(self) -> Self:
        if len(set(self.allowed_roles)) != len(self.allowed_roles):
            raise ValueError("allowed_roles must not contain duplicates")
        return self


class UploadAccepted(Contract):
    document_id: UUID
    task_id: UUID
    status: Literal["queued"]
    message: Text


class EvidenceChunk(Contract):
    citation_id: int = Field(ge=1, strict=True)
    chunk_id: UUID
    document_id: UUID
    document_title: Text
    chunk_index: int = Field(ge=0, strict=True)
    page: int | None = Field(default=None, ge=1, strict=True)
    content: Text = Field(max_length=8000)
    similarity_score: float = Field(ge=-1, le=1)


class GenerationRequest(Contract):
    """Only evidence already authorized by the backend crosses this boundary."""
    question: Text = Field(max_length=4000)
    evidence: list[EvidenceChunk] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def unique_evidence_ids(self) -> Self:
        if len({x.citation_id for x in self.evidence}) != len(self.evidence):
            raise ValueError("citation IDs must be unique")
        if len({x.chunk_id for x in self.evidence}) != len(self.evidence):
            raise ValueError("chunk IDs must be unique")
        return self


def _check_answer_state(
    answer: str | None, citations: Sequence[object], abstained: bool, reason: str | None
) -> None:
    if abstained:
        if answer is not None or citations or not reason:
            raise ValueError("abstention requires null answer, empty citations and a reason")
    elif not answer or not citations or reason is not None:
        raise ValueError("an answer requires evidence citations and no abstention reason")


def _check_markers(answer: str | None, ids: Sequence[int]) -> None:
    markers = {int(x) for x in re.findall(r"\[(\d+)\]", answer or "")}
    if markers != set(ids):
        raise ValueError("inline citation markers must match the cited ID set")


class GenerationResult(Contract):
    answer: Text | None
    cited_ids: list[Annotated[int, Field(ge=1, strict=True)]] = Field(max_length=20)
    abstained: bool = Field(strict=True)
    abstention_reason: Text | None = None

    @model_validator(mode="after")
    def consistent_result(self) -> Self:
        if any(i < 1 for i in self.cited_ids) or len(set(self.cited_ids)) != len(self.cited_ids):
            raise ValueError("cited_ids must be unique positive integers")
        _check_answer_state(self.answer, self.cited_ids, self.abstained, self.abstention_reason)
        _check_markers(self.answer, self.cited_ids)
        return self


def validate_generation_result(
    result: GenerationResult, request: GenerationRequest
) -> GenerationResult:
    """Check membership in authorized evidence; this does not prove claim support."""
    allowed = {item.citation_id for item in request.evidence}
    if not set(result.cited_ids).issubset(allowed):
        raise ValueError("generation cited an ID outside the supplied evidence")
    return result


class Citation(Contract):
    id: int = Field(ge=1, strict=True)
    chunk_id: UUID
    document_id: UUID
    document_title: Text
    chunk_index: int = Field(ge=0, strict=True)
    page: int | None = Field(default=None, ge=1, strict=True)
    excerpt: Text
    similarity_score: float = Field(ge=-1, le=1)


class QueryMeta(Contract):
    retrieval_time_ms: float = Field(ge=0)
    generation_time_ms: float = Field(ge=0)
    model: Text


class QueryResponse(Contract):
    answer: Text | None
    citations: list[Citation] = Field(max_length=20)
    abstained: bool = Field(strict=True)
    abstention_reason: Text | None = None
    session_id: UUID
    meta: QueryMeta

    @model_validator(mode="after")
    def consistent_response(self) -> Self:
        ids = [c.id for c in self.citations]
        if len(set(ids)) != len(ids):
            raise ValueError("citation IDs must be unique")
        _check_answer_state(self.answer, self.citations, self.abstained, self.abstention_reason)
        _check_markers(self.answer, ids)
        return self


class DocumentSummary(Contract):
    id: UUID
    title: Text = Field(max_length=512)
    source_type: Literal["pdf", "docx"]
    status: DocumentState
    allowed_roles: list[Role] = Field(min_length=1)
    chunk_count: int = Field(ge=0, strict=True)
    created_at: AwareDatetime

    @field_validator("created_at", mode="after")
    @classmethod
    def _normalize_created_at_utc(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)


class DocumentDetail(DocumentSummary):
    description: Text | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class PageMeta(Contract):
    total: int = Field(ge=0, strict=True)
    limit: int = Field(default=20, ge=1, le=100, strict=True)
    offset: int = Field(default=0, ge=0, strict=True)


class DocumentList(Contract):
    data: list[DocumentSummary]
    meta: PageMeta

    @model_validator(mode="after")
    def consistent_page(self) -> Self:
        if len(self.data) > self.meta.limit:
            raise ValueError("page data exceeds limit")
        if self.data and self.meta.offset + len(self.data) > self.meta.total:
            raise ValueError("page exceeds total")
        return self


class DocumentStatus(Contract):
    document_id: UUID
    status: DocumentState
    chunks_processed: int = Field(ge=0, strict=True)
    total_chunks: int | None = Field(default=None, ge=0, strict=True)
    progress_percent: int | None = Field(default=None, ge=0, le=100, strict=True)
    failure_code: Literal["INVALID_FILE", "PROCESSING_FAILED", "INTERRUPTED"] | None = None
    failure_message: Text | None = None

    @model_validator(mode="after")
    def consistent_progress(self) -> Self:
        if self.status == "failed":
            if not self.failure_code or not self.failure_message:
                raise ValueError("failed status requires a safe failure code and message")
        elif self.failure_code is not None or self.failure_message is not None:
            raise ValueError("failure details are only valid in failed status")
        if self.total_chunks is not None and self.chunks_processed > self.total_chunks:
            raise ValueError("processed chunks exceeds total")
        if self.status == "complete" and (
            self.total_chunks is None or self.chunks_processed != self.total_chunks
            or self.progress_percent != 100
        ):
            raise ValueError("complete requires known totals, all processed and progress=100")
        return self


class ErrorResponse(Contract):
    detail: Text
    code: Literal[
        "VALIDATION_ERROR", "INVALID_FILE", "FILE_TOO_LARGE", "UNAUTHORIZED",
        "FORBIDDEN", "NOT_FOUND", "CONFLICT", "PROVIDER_UNAVAILABLE",
        "INVALID_CITATIONS", "INTERNAL_ERROR",
    ]
    request_id: UUID


CONTRACT_MODELS = {
    cls.__name__: cls for cls in (
        ActorContext, QueryRequest, UploadMetadata, UploadAccepted, EvidenceChunk,
        GenerationRequest, GenerationResult, Citation, QueryMeta, QueryResponse,
        DocumentSummary, DocumentDetail, PageMeta, DocumentList, DocumentStatus,
        ErrorResponse,
    )
}
