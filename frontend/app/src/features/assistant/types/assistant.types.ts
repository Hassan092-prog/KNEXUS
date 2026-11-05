/**
 * Assistant (query) API contracts mirrored from `contracts/phase1/models.py`
 * (QueryRequest, QueryResponse, Citation, QueryMeta). Verified against
 * `backend/app/api/v1/endpoints/query.py`.
 */

export interface QueryRequest {
  /** 1–4000 characters after backend trim. */
  question: string
  /** 1–20; backend default is 5. */
  top_k?: number
  /**
   * Phase 1 accepts `false` only — `stream: true` is rejected with 422.
   * Omit to use the backend default.
   */
  stream?: false
}

export interface Citation {
  id: number
  chunk_id: string
  document_id: string
  document_title: string
  chunk_index: number
  /** Page numbers exist for PDFs only; DOCX citations are null. */
  page: number | null
  excerpt: string
  /** Cosine similarity, −1..1. */
  similarity_score: number
}

export interface QueryMeta {
  retrieval_time_ms: number
  generation_time_ms: number
  /** Varies by provider (e.g. "fake", "llama3.2:3b", hosted ids). Never hardcode. */
  model: string
}

export interface QueryResponse {
  /** Inline `[N]` markers match citation ids. Null when abstained. */
  answer: string | null
  citations: Citation[]
  /** A 200-with-abstention is a valid response, not an error. */
  abstained: boolean
  abstention_reason: string | null
  session_id: string
  meta: QueryMeta
}
