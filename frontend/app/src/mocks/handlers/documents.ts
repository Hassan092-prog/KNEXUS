import { uploadMetadataSchema } from "@/lib/api/contracts"
import type { DocumentDetail, DocumentListParams, DocumentState, DocumentStatusResponse, DocumentSummary, UploadAcceptedResponse, UploadMetadataInput } from "@/features/documents/types/document.types"
import { randomUuid } from "@/lib/utils/random"

import { mockDelay } from "@/lib/api/mode"
import {
  advanceLifecycle,
  CANONICAL_DETAIL,
  CANONICAL_STATUS_COMPLETE,
  CANONICAL_STATUS_FAILED,
  CANONICAL_STATUS_QUEUED,
  filenameTriggersFailure,
  findSummary,
  getSummaries,
  getUploadLifecycle,
  lifecycleState,
  notFoundError,
  registerUpload,
  simulateUploadFailure,
  validationError,
} from "@/mocks/store"

/**
 * Mock handlers for the document feature operations. Handlers return data in
 * contract shapes WITHOUT re-validating — `mock-server.ts` runs every output
 * through the Zod schemas before it reaches the UI belt-and-braces style.
 *
 * Composition sites (runtime-composed values that have no verbatim fixture)
 * are flagged inline and use ONLY contract-defined fields.
 */

/** Verbatim `document-status-queued.json` field values (per-state template). */
const QUEUED_TEMPLATE = {
  chunks_processed: CANONICAL_STATUS_QUEUED.chunks_processed,
  total_chunks: CANONICAL_STATUS_QUEUED.total_chunks,
  progress_percent: CANONICAL_STATUS_QUEUED.progress_percent,
}

export const documentHandlers = {
  async listDocuments(params: DocumentListParams = {}): Promise<{
    data: DocumentSummary[]
    meta: { total: number; limit: number; offset: number }
  }> {
    await mockDelay()
    const limit = params.limit ?? 20
    const offset = params.offset ?? 0
    const all = getSummaries()
    return {
      data: all.slice(offset, offset + limit).map((summary) => ({ ...summary, allowed_roles: [...summary.allowed_roles] })),
      meta: { total: all.length, limit, offset },
    }
  },

  async getDocument(documentId: string): Promise<DocumentDetail> {
    await mockDelay()
    const summary = findSummary(documentId)
    if (!summary) {
      throw notFoundError()
    }
    if (documentId === CANONICAL_DETAIL.id) {
      // Canonical `document-detail.json`, with the live store status.
      return { ...CANONICAL_DETAIL, status: summary.status }
    }
    // Front-end composite: detail fields for documents without a canonical
    // details fixture, using their contract-defined empty values.
    return { ...summary, description: null, metadata: {} }
  },

  async getDocumentStatus(documentId: string): Promise<DocumentStatusResponse> {
    await mockDelay()
    const summary = findSummary(documentId)
    if (!summary) {
      throw notFoundError()
    }

    const lifecycle = getUploadLifecycle(documentId)
    if (lifecycle) {
      advanceLifecycle(documentId)
      return uploadedStatus(summary.id, lifecycle)
    }

    // Seeded documents keep their fixture state, resolved per state below.
    if (summary.status === "complete") {
      // Contract: complete ⇒ totals known, all processed, progress=100.
      // Composite: totals come from this document's own chunk_count.
      return {
        document_id: summary.id,
        status: "complete",
        chunks_processed: summary.chunk_count,
        total_chunks: summary.chunk_count,
        progress_percent: CANONICAL_STATUS_COMPLETE.progress_percent,
        failure_code: null,
        failure_message: null,
      }
    }
    if (summary.status === "failed") {
      // Verbatim canonical `document-status-failed.json` values.
      return {
        document_id: summary.id,
        status: "failed",
        chunks_processed: CANONICAL_STATUS_FAILED.chunks_processed,
        total_chunks: CANONICAL_STATUS_FAILED.total_chunks,
        progress_percent: CANONICAL_STATUS_FAILED.progress_percent,
        failure_code: CANONICAL_STATUS_FAILED.failure_code,
        failure_message: CANONICAL_STATUS_FAILED.failure_message,
      }
    }
    if (summary.status === "queued") {
      return {
        document_id: summary.id,
        status: "queued",
        ...QUEUED_TEMPLATE,
        failure_code: null,
        failure_message: null,
      }
    }
    // Processing seed: composite derived from this document's chunk_count at
    // a 1/3 checkpoint (same semantics as the canonical processing template).
    const chunks = Math.max(1, Math.floor(summary.chunk_count / 3))
    return {
      document_id: summary.id,
      status: "processing",
      chunks_processed: chunks,
      total_chunks: summary.chunk_count,
      progress_percent: Math.round((chunks / summary.chunk_count) * 100),
      failure_code: null,
      failure_message: null,
    }
  },

  async uploadDocument(
    file: File,
    metadata: UploadMetadataInput,
  ): Promise<UploadAcceptedResponse> {
    await mockDelay()

    const parsed = uploadMetadataSchema.safeParse(metadata)
    if (!parsed.success) {
      // Canonical `validation-error.json` semantics for contract-breaking input.
      throw validationError()
    }

    const extension = extensionOf(file.name)
    // Uploads are accepted and tracked in the store only — fixture files are
    // never written. The accepted response matches the canonical
    // `upload-accepted.json` shape; ids are composed fresh per request, as on
    // the backend.
    const documentId = randomUuid()
    const summary: DocumentSummary = {
      id: documentId,
      title:
        parsed.data.title ??
        (file.name.replace(/\.[^.]+$/, "") || "Uploaded document"),
      source_type: extension,
      status: "queued",
      allowed_roles: [...parsed.data.allowed_roles],
      chunk_count: 0,
      created_at: new Date().toISOString(),
    }
    registerUpload(summary, file.size)

    if (filenameTriggersFailure(file.name)) {
      // Documented simulation: ingestion then fails with the canonical
      // INVALID_FILE failure shape (upload itself still returns accepted).
      simulateUploadFailure(documentId)
    }

    return {
      document_id: documentId,
      task_id: randomUuid(),
      status: "queued",
      message: "Document received. Processing in background.",
    }
  },
}

/** Status for an uploaded document according to its poll progression. */
function uploadedStatus(
  documentId: string,
  lifecycle: { pollCount: number; totalChunks: number; failed: boolean },
): DocumentStatusResponse {
  if (lifecycle.failed) {
    // Canonical failed shape, but with a failed upload's fresh totals context.
    return {
      document_id: documentId,
      status: "failed",
      chunks_processed: CANONICAL_STATUS_FAILED.chunks_processed,
      total_chunks: CANONICAL_STATUS_FAILED.total_chunks,
      progress_percent: CANONICAL_STATUS_FAILED.progress_percent,
      failure_code: CANONICAL_STATUS_FAILED.failure_code,
      failure_message: CANONICAL_STATUS_FAILED.failure_message,
    }
  }
  const state = lifecycleState(lifecycle)
  if (state === "complete") {
    // Contract-consistent terminal state: totals == processed, progress=100.
    return {
      document_id: documentId,
      status: "complete",
      chunks_processed: lifecycle.totalChunks,
      total_chunks: lifecycle.totalChunks,
      progress_percent: CANONICAL_STATUS_COMPLETE.progress_percent,
      failure_code: null,
      failure_message: null,
    }
  }
  if (state === "processing") {
    // Composite: 2/3 checkpoint computed from the simulated chunk total.
    const chunks = Math.max(1, Math.floor((lifecycle.totalChunks * 2) / 3))
    return {
      document_id: documentId,
      status: "processing",
      chunks_processed: chunks,
      total_chunks: lifecycle.totalChunks,
      progress_percent: Math.round((chunks / lifecycle.totalChunks) * 100),
      failure_code: null,
      failure_message: null,
    }
  }
  // Still queued (first poll).
  return {
    document_id: documentId,
    status: "queued",
    ...QUEUED_TEMPLATE,
    failure_code: null,
    failure_message: null,
  }
}

function extensionOf(fileName: string): "pdf" | "docx" {
  const lower = fileName.toLowerCase()
  if (lower.endsWith(".docx")) return "docx"
  // Composite: only pdf/docx exist in the contract; other names are treated
  // as the pdf source type for simulation purposes.
  return "pdf"
}

export type { DocumentState }
