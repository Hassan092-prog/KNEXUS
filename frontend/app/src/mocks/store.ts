import { apiErrorResponseSchema, documentDetailSchema, documentListSchema, documentStatusSchema, queryResponseSchema } from "@/lib/api/contracts"
import { MockApiError } from "@/lib/api/error"
import type { DocumentState, DocumentSummary } from "@/features/documents/types/document.types"
import { randomUuid } from "@/lib/utils/random"

import documentListRaw from "@/mocks/data/document-list.json"
import documentDetailRaw from "@/mocks/data/document-detail.json"
import documentStatusQueuedRaw from "@/mocks/data/document-status-queued.json"
import documentStatusProcessingRaw from "@/mocks/data/document-status-processing.json"
import documentStatusCompleteRaw from "@/mocks/data/document-status-complete.json"
import documentStatusFailedRaw from "@/mocks/data/document-status-failed.json"
import queryAnswerRaw from "@/mocks/data/query-answer.json"
import queryAbstentionRaw from "@/mocks/data/query-abstention.json"
import providerErrorRaw from "@/mocks/data/provider-error.json"
import validationErrorRaw from "@/mocks/data/validation-error.json"

/**
 * The mock in-memory data store.
 *
 * Seeds are deep copies of the JSON fixtures in `mocks/data/` — every fixture
 * is parsed through the same Zod contract schemas used for live responses, so
 * the mock cannot drift from the canonical contract. Runtime operations
 * (uploads, status polls) mutate ONLY this store; the JSON fixture files are
 * never written. Responses composed at runtime use exclusively contract-
 * defined fields (each composition site is flagged in `handlers/`).
 */

const SUMMARY_LIST_SOURCE = documentListSchema.parse(documentListRaw)
export const CANONICAL_DETAIL = documentDetailSchema.parse(documentDetailRaw)
export const CANONICAL_STATUS_QUEUED = documentStatusSchema.parse(documentStatusQueuedRaw)
export const CANONICAL_STATUS_PROCESSING = documentStatusSchema.parse(documentStatusProcessingRaw)
export const CANONICAL_STATUS_COMPLETE = documentStatusSchema.parse(documentStatusCompleteRaw)
export const CANONICAL_STATUS_FAILED = documentStatusSchema.parse(documentStatusFailedRaw)
export const CANONICAL_QUERY_ANSWER = queryResponseSchema.parse(queryAnswerRaw)
export const CANONICAL_QUERY_ABSTENTION = queryResponseSchema.parse(queryAbstentionRaw)
/** Canonical error envelopes, served verbatim when their trigger fires. */
export const CANONICAL_PROVIDER_ERROR = apiErrorResponseSchema.parse(providerErrorRaw)
export const CANONICAL_VALIDATION_ERROR = apiErrorResponseSchema.parse(validationErrorRaw)

/* ----------------------------- trigger vocabulary ----------------------------- */

/**
 * Documented front-end testing triggers (not backend behavior): the assistant
 * abstains on retrieval evidence in reality — here a keyword selects the
 * canonical abstention fixture. "provider unavailable" serves the canonical
 * `provider-error.json` 503 envelope; "network failure" raises a transport
 * error so the error pipeline can be exercised without a backend.
 */
export const ABSTENTION_KEYWORDS = ["abstain", "nothing", "unrelated", "irrelevant", "no evidence"] as const
export const PROVIDER_TRIGGER = "provider unavailable"
export const NETWORK_TRIGGER = "network failure"
/** Filenames containing this marker simulate a failed ingestion run. */
export const FAILURE_FILENAME_MARKER = "fail"

export function questionTriggersAbstention(question: string): boolean {
  const lower = question.toLowerCase()
  return ABSTENTION_KEYWORDS.some((keyword) => lower.includes(keyword))
}

export function questionTriggersProviderError(question: string): boolean {
  return question.toLowerCase().includes(PROVIDER_TRIGGER)
}

export function questionTriggersNetworkFailure(question: string): boolean {
  return question.toLowerCase().includes(NETWORK_TRIGGER)
}

export function filenameTriggersFailure(fileName: string): boolean {
  return fileName.toLowerCase().includes(FAILURE_FILENAME_MARKER)
}

/* -------------------------------- mock errors -------------------------------- */

function freshEnvelope(detail: string, code: string, status: number): MockApiError {
  const response = apiErrorResponseSchema.parse({
    detail,
    code,
    request_id: randomUuid(),
  })
  return new MockApiError(response, status)
}

/** Composed detail text (NOT_FOUND has no canonical fixture wording). */
export function notFoundError(): MockApiError {
  return freshEnvelope("The requested document was not found.", "NOT_FOUND", 404)
}

/** Canonical `validation-error.json` envelope except for a fresh request id. */
export function validationError(): MockApiError {
  return freshEnvelope(CANONICAL_VALIDATION_ERROR.detail, CANONICAL_VALIDATION_ERROR.code, 422)
}

/** Canonical `provider-error.json` envelope except for a fresh request id. */
export function providerUnavailableError(): MockApiError {
  const response = apiErrorResponseSchema.parse({
    ...CANONICAL_PROVIDER_ERROR,
    request_id: randomUuid(),
  })
  return new MockApiError(response, 503)
}

/* --------------------------------- the store --------------------------------- */

/**
 * Per-upload ingestion lifecycle tracking. `pollCount` advances on every
 * status request so successive polls progress queued → processing →
 * complete, exercising bounded-polling states without a scheduler.
 */
interface UploadLifecycle {
  pollCount: number
  totalChunks: number
  /** Simulated pipeline failure (filename trigger); status is the failed template. */
  failed: boolean
}

let summaries: DocumentSummary[] = []
const lifecycles = new Map<string, UploadLifecycle>()

/** Rebuilds the in-memory store from the fixtures; used at import and in tests. */
export function resetMockStore(): void {
  summaries = SUMMARY_LIST_SOURCE.data.map((summary) => ({ ...summary, allowed_roles: [...summary.allowed_roles] }))
  lifecycles.clear()
}

export function getSummaries(): DocumentSummary[] {
  return summaries
}

export function findSummary(documentId: string): DocumentSummary | undefined {
  return summaries.find((summary) => summary.id === documentId)
}

export function getUploadLifecycle(documentId: string): UploadLifecycle | undefined {
  return lifecycles.get(documentId)
}

/**
 * Front-end composite: registers a freshly uploaded document (backed only by
 * contract-defined fields). The chunk total is derived from the file size so
 * each upload gets a realistic, deterministic processing profile.
 */
export function registerUpload(summary: DocumentSummary, fileSizeBytes: number): void {
  const totalChunks = Math.min(40, Math.max(1, Math.round(fileSizeBytes / 2048)))
  summaries = [summary, ...summaries]
  lifecycles.set(summary.id, {
    pollCount: 0,
    totalChunks,
    failed: false,
  })
}

export function simulateUploadFailure(documentId: string): void {
  const lifecycle = lifecycles.get(documentId)
  if (lifecycle) {
    lifecycle.failed = true
  }
  const summary = findSummary(documentId)
  if (summary) {
    summary.status = "failed"
  }
}

/** Advances the lifecycle before each status poll of an uploaded document. */
export function advanceLifecycle(documentId: string): UploadLifecycle {
  const lifecycle = lifecycles.get(documentId)
  if (!lifecycle) {
    throw notFoundError()
  }
  if (!lifecycle.failed) {
    lifecycle.pollCount += 1
    const summary = findSummary(documentId)
    if (summary) {
      if (lifecycle.pollCount >= 3) {
        summary.status = "complete"
        summary.chunk_count = lifecycle.totalChunks
      } else if (lifecycle.pollCount >= 2) {
        summary.status = "processing"
      }
    }
  }
  return lifecycle
}

export function lifecycleState(lifecycle: UploadLifecycle): DocumentState {
  if (lifecycle.failed) return "failed"
  if (lifecycle.pollCount >= 3) return "complete"
  if (lifecycle.pollCount >= 2) return "processing"
  return "queued"
}

resetMockStore()
