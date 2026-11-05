"""Stable application import boundary for the accepted Phase 1 contracts.

The authoritative Pydantic definitions remain in contracts/phase1/models.py;
this package re-exports them so backend features share one set of validators.
"""
from contracts.phase1.models import (
    ActorContext,
    Citation,
    DocumentDetail,
    DocumentList,
    DocumentStatus,
    DocumentSummary,
    ErrorResponse,
    EvidenceChunk,
    GenerationRequest,
    GenerationResult,
    PageMeta,
    QueryMeta,
    QueryRequest,
    QueryResponse,
    Role,
    UploadAccepted,
    UploadMetadata,
    validate_generation_result,
)

__all__ = [
    "ActorContext",
    "Citation",
    "DocumentDetail",
    "DocumentList",
    "DocumentStatus",
    "DocumentSummary",
    "ErrorResponse",
    "EvidenceChunk",
    "GenerationRequest",
    "GenerationResult",
    "PageMeta",
    "QueryMeta",
    "QueryRequest",
    "QueryResponse",
    "Role",
    "UploadAccepted",
    "UploadMetadata",
    "validate_generation_result",
]
