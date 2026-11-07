/**
 * Document contracts for feature code. Shapes are inferred once in
 * `lib/api/contracts.ts` (mirroring `contracts/phase1/models.py` and verified
 * against `backend/app/api/v1/endpoints/documents.py`) and aliased here — no
 * hand-written duplicates that could drift from the contract.
 */
import type {
  DocumentDetail as ContractDocumentDetail,
  DocumentFailureCode,
  DocumentList as ContractDocumentList,
  DocumentRole,
  DocumentState,
  DocumentSourceType,
  DocumentStatus as ContractDocumentStatus,
  DocumentSummary,
  UploadAccepted as ContractUploadAccepted,
} from "@/lib/api/contracts"

/** Exactly the values permitted by `contracts/phase1/models.py`. */
export type { DocumentRole, DocumentState, DocumentSourceType, DocumentFailureCode, DocumentSummary }

export type DocumentDetail = ContractDocumentDetail
export type PageMeta = ContractDocumentList["meta"]
export type DocumentListResponse = ContractDocumentList
export type DocumentStatusResponse = ContractDocumentStatus
export type UploadAcceptedResponse = ContractUploadAccepted

export type DocumentListParams = {
  /** Covers the full 1–100 limit range validated by the backend. */
  limit?: number
  offset?: number
}

/** Multipart upload metadata; repeated `allowed_roles` form fields. */
export interface UploadMetadataInput {
  allowed_roles: DocumentRole[]
  title?: string | undefined
  description?: string | undefined
}
