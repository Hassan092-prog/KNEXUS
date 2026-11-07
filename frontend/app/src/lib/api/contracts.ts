import { z } from "zod"

/**
 * Zod contracts mirroring `contracts/phase1/models.py` — the canonical Phase 1
 * source of truth. Field names, nullability, enums, bounds and cross-field
 * invariants match the backend exactly; strict objects reject unknown fields
 * just like `extra="forbid"`.
 *
 * Every live response and every mock fixture / handler output is parsed with
 * these schemas at the API boundary. Types consumed by feature code are
 * inferred here (single definition, no hand-written duplicates).
 */

/* ------------------------------- primitives ------------------------------- */

export const HTTP_STATUS = {
  BAD_REQUEST: 400,
  NOT_FOUND: 404,
  FORBIDDEN: 403,
  UNAUTHORIZED: 401,
  CONFLICT: 409,
  TOO_LARGE: 413,
  VALIDATION: 422,
  INVALID_CITATIONS: 502,
  PROVIDER_UNAVAILABLE: 503,
  TIMEOUT: 504,
  INTERNAL: 500,
} as const

/** Literal `Role` values permitted by the upload contract. */
export const DOCUMENT_ROLES = ["employee", "manager", "orgadmin", "superadmin"] as const
export const roleSchema = z.enum(DOCUMENT_ROLES)
export type DocumentRole = z.infer<typeof roleSchema>

export const documentStateSchema = z.enum(["queued", "processing", "complete", "failed"])
export type DocumentState = z.infer<typeof documentStateSchema>

export const documentSourceTypeSchema = z.enum(["pdf", "docx"])
export type DocumentSourceType = z.infer<typeof documentSourceTypeSchema>

export const documentFailureCodeSchema = z.enum([
  "INVALID_FILE",
  "PROCESSING_FAILED",
  "INTERRUPTED",
])
export type DocumentFailureCode = z.infer<typeof documentFailureCodeSchema>

/** `ErrorResponse` code enum, exported for exhaustive message mapping. */
export const API_ERROR_CODES = [
  "VALIDATION_ERROR",
  "INVALID_FILE",
  "FILE_TOO_LARGE",
  "UNAUTHORIZED",
  "FORBIDDEN",
  "NOT_FOUND",
  "CONFLICT",
  "PROVIDER_UNAVAILABLE",
  "INVALID_CITATIONS",
  "INTERNAL_ERROR",
] as const
export type ApiErrorCode = (typeof API_ERROR_CODES)[number]

/* --------------------------- echoed request models --------------------------- */

/**
 * Query contract (QueryRequest). Phase 1 accepts `stream: false` only; a
 * `stream: true` submission is a frontend bug, so the schema forbids it.
 */
export const queryRequestSchema = z.strictObject({
  /** Backend trims whitespace; 1–4000 characters after trim. */
  question: z.string().trim().min(1).max(4000),
  /** Backend default is 5; 1–20. */
  top_k: z.int().min(1).max(20).default(5).optional(),
  /** Phase 1 baseline accepts `false` only (`stream: true` is a 422). */
  stream: z.literal(false).default(false).optional(),
})
export type QueryRequest = z.infer<typeof queryRequestSchema>

/**
 * Upload metadata contract (UploadMetadata). Mirrors multipart semantics:
 * `allowed_roles` is a repeated form field list, not a JSON string, and must
 * contain unique roles.
 */
export const uploadMetadataSchema = z.strictObject({
  title: z.string().trim().min(1).max(512).optional(),
  allowed_roles: z.array(roleSchema).min(1),
  description: z.string().trim().min(1).max(2000).optional(),
}).superRefine((value, ctx) => {
  if (new Set(value.allowed_roles).size !== value.allowed_roles.length) {
    ctx.addIssue({ code: "custom", path: ["allowed_roles"], message: "allowed_roles must not contain duplicates" })
  }
})
export type UploadMetadata = z.infer<typeof uploadMetadataSchema>

/* ------------------------------ document models ------------------------------ */

const documentSummaryFields = {
  id: z.uuid(),
  title: z.string().trim().min(1).max(512),
  source_type: documentSourceTypeSchema,
  status: documentStateSchema,
  allowed_roles: z.array(roleSchema).min(1),
  chunk_count: z.int().min(0),
  /** Timezone-aware UTC timestamp. */
  created_at: z.iso.datetime(),
}

export const documentSummarySchema = z.strictObject(documentSummaryFields)
export type DocumentSummary = z.infer<typeof documentSummarySchema>

export const documentDetailSchema = z.strictObject({
  ...documentSummaryFields,
  description: z.string().trim().min(1).max(2000).nullish().transform((v) => v ?? null),
  metadata: z.record(z.string(), z.json()),
})
export type DocumentDetail = z.infer<typeof documentDetailSchema>

export const pageMetaSchema = z.strictObject({
  total: z.int().min(0),
  limit: z.int().min(1).max(100).default(20),
  offset: z.int().min(0).default(0),
})

export const documentListSchema = z.strictObject({
  data: z.array(documentSummarySchema),
  meta: pageMetaSchema,
}).superRefine((value, ctx) => {
  if (value.data.length > value.meta.limit) {
    ctx.addIssue({ code: "custom", path: ["data"], message: "page data exceeds limit" })
  }
  if (
    value.data.length > 0 &&
    value.meta.offset + value.data.length > value.meta.total
  ) {
    ctx.addIssue({ code: "custom", path: ["data"], message: "page exceeds total" })
  }
})
export type DocumentList = z.infer<typeof documentListSchema>

/**
 * Processing status (DocumentStatus). Guards the backend's cross-field rules:
 * failure details only exist for `failed`; complete requires known totals, all
 * chunks processed and progress = 100.
 */
export const documentStatusSchema = z.strictObject({
  document_id: z.uuid(),
  status: documentStateSchema,
  chunks_processed: z.int().min(0),
  total_chunks: z.int().min(0).nullable(),
  progress_percent: z.int().min(0).max(100).nullable(),
  failure_code: documentFailureCodeSchema.nullable(),
  failure_message: z.string().trim().min(1).nullable(),
}).superRefine((value, ctx) => {
  if (value.status === "failed") {
    if (value.failure_code === null || value.failure_message === null) {
      ctx.addIssue({ code: "custom", message: "failed status requires a safe failure code and message" })
    }
    return
  }
  if (value.failure_code !== null || value.failure_message !== null) {
    ctx.addIssue({ code: "custom", message: "failure details are only valid in failed status" })
  }
  if (
    value.status === "complete" &&
    (value.total_chunks === null ||
      value.chunks_processed !== value.total_chunks ||
      value.progress_percent !== 100)
  ) {
    ctx.addIssue({ code: "custom", message: "complete requires known totals, all processed and progress=100" })
  }
})
export type DocumentStatus = z.infer<typeof documentStatusSchema>

export const uploadAcceptedSchema = z.strictObject({
  document_id: z.uuid(),
  task_id: z.uuid(),
  status: z.literal("queued"),
  message: z.string().trim().min(1),
})
export type UploadAccepted = z.infer<typeof uploadAcceptedSchema>

/* ------------------------------- query models ------------------------------- */

export const citationSchema = z.strictObject({
  id: z.int().min(1),
  chunk_id: z.uuid(),
  document_id: z.uuid(),
  document_title: z.string().trim().min(1),
  chunk_index: z.int().min(0),
  /** Page numbers exist for PDFs only; DOCX citations are null. */
  page: z.int().min(1).nullable(),
  excerpt: z.string().trim().min(1).max(8000),
  /** Cosine similarity, −1..1. */
  similarity_score: z.number().min(-1).max(1),
})
export type Citation = z.infer<typeof citationSchema>

export const queryMetaSchema = z.strictObject({
  retrieval_time_ms: z.number().min(0),
  generation_time_ms: z.number().min(0),
  /** Varies by provider (e.g. "fake", "llama3.2:3b"). Never hardcoded. */
  model: z.string().trim().min(1),
})

/**
 * QueryResponse (client-facing subset of GenerationResult). Guards the
 * backend's answer/abstention invariants: abstention requires a null answer,
 * empty citations and a non-empty reason; an answer requires citations and no
 * reason; inline `[N]` markers must match the citation ID set exactly.
 */
export const queryResponseSchema = z.strictObject({
  answer: z.string().trim().min(1).nullable(),
  citations: z.array(citationSchema).max(20),
  abstained: z.boolean(),
  abstention_reason: z.string().trim().min(1).nullable(),
  /** Fresh response correlation UUID — not a stored conversation id. */
  session_id: z.uuid(),
  meta: queryMetaSchema,
}).superRefine((value, ctx) => {
  if (value.abstained) {
    if (value.answer !== null || value.citations.length > 0 || value.abstention_reason === null) {
      ctx.addIssue({
        code: "custom",
        message: "abstention requires null answer, empty citations and a reason",
      })
    }
    return
  }
  if (!value.answer || value.citations.length === 0 || value.abstention_reason !== null) {
    ctx.addIssue({
      code: "custom",
      message: "an answer requires evidence citations and no abstention reason",
    })
  }
  const markers = new Set(
    (value.answer?.match(/\[(\d+)\]/g) ?? []).map((m) => Number.parseInt(m.slice(1, -1), 10)).filter((id) => Number.isInteger(id)),
  )
  const ids = new Set(value.citations.map((c) => c.id))
  if (markers.size !== ids.size || [...markers].some((m) => !ids.has(m))) {
    ctx.addIssue({
      code: "custom",
      message: "inline citation markers must match the cited ID set",
    })
  }
})
export type QueryResponse = z.infer<typeof queryResponseSchema>

/* --------------------------------- errors --------------------------------- */

/**
 * Canonical client-visible error envelope, produced by every failure route
 * (`backend/app/api/errors.py`), including FastAPI validation errors.
 */
export const apiErrorResponseSchema = z.strictObject({
  detail: z.string().trim().min(1),
  code: z.enum(API_ERROR_CODES),
  request_id: z.uuid(),
})
export type ApiErrorResponse = z.infer<typeof apiErrorResponseSchema>
