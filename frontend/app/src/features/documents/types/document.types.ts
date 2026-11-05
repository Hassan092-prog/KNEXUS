/**
 * Document API contracts mirrored from `contracts/phase1/models.py`
 * (DocumentSummary, DocumentDetail, DocumentList, PageMeta, DocumentStatus,
 * UploadAccepted). Verified against `backend/app/api/v1/endpoints/documents.py`.
 */

/** Exactly the values permitted by `contracts/phase1/models.py`. */
export type DocumentRole = "employee" | "manager" | "orgadmin" | "superadmin"

/** Ingestion lifecycle states; `complete` and `failed` are terminal. */
export type DocumentState = "queued" | "processing" | "complete" | "failed"

export type DocumentSourceType = "pdf" | "docx"

/** Safe failure codes emitted by the ingestion pipeline. */
export type DocumentFailureCode = "INVALID_FILE" | "PROCESSING_FAILED" | "INTERRUPTED"

export interface DocumentSummary {
  id: string
  title: string
  source_type: DocumentSourceType
  status: DocumentState
  allowed_roles: DocumentRole[]
  chunk_count: number
  created_at: string
}

export interface DocumentDetail extends DocumentSummary {
  description: string | null
  metadata: Record<string, unknown>
}

export interface PageMeta {
  total: number
  limit: number
  offset: number
}

export interface DocumentListResponse {
  data: DocumentSummary[]
  meta: PageMeta
}

export type DocumentListParams = {
  /** Covers full 1–100 range validated by the backend. */
  limit?: number
  offset?: number
}

export interface DocumentStatusResponse {
  document_id: string
  status: DocumentState
  chunks_processed: number
  total_chunks: number | null
  progress_percent: number | null
  failure_code: DocumentFailureCode | null
  failure_message: string | null
}

export interface UploadAcceptedResponse {
  document_id: string
  task_id: string
  status: "queued"
  message: string
}

/** Multipart upload metadata; repeated `allowed_roles` form fields. */
export interface UploadMetadataInput {
  allowed_roles: DocumentRole[]
  title?: string | undefined
  description?: string | undefined
}
