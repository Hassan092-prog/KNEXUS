import { apiClient, buildUploadFormData } from "@/lib/api/client"
import {
  documentDetailSchema,
  documentListSchema,
  documentStatusSchema,
  uploadAcceptedSchema,
} from "@/lib/api/contracts"
import { ApiError } from "@/lib/api/error"

import type { z } from "zod"

import type { UploadTransferOptions } from "@/features/documents/services/document.api"
import type {
  DocumentDetail,
  DocumentListParams,
  DocumentListResponse,
  DocumentStatusResponse,
  UploadAcceptedResponse,
  UploadMetadataInput,
} from "@/features/documents/types/document.types"

/**
 * Live implementation of the DocumentApi against the real KNEXUS routes
 * (`GET /documents`, `GET /documents/{id}`, `GET /documents/{id}/status`,
 * `POST /documents/upload`). Every response body is validated against the
 * canonical contract schema before it reaches the UI; a contract violation is
 * a hard error, never silently coerced.
 */

/**
 * Asserts a live response against its canonical contract schema. Returns the
 * typed payload, or throws an `ApiError` that keeps the HTTP status and shows
 * a safe message (schema internals stay in the console for debugging).
 */
export function parseOrThrow<T>(schema: z.ZodType<T>, data: unknown): T {
  const result = schema.safeParse(data)
  if (result.success) {
    return result.data
  }
  if (import.meta.env.DEV) {
    console.error("[knexus] response failed contract validation", result.error.issues)
  }
  throw new ApiError({
    detail: "The backend sent an unexpected response. It may be running an incompatible version.",
  })
}

export const documentLiveApi = {
  async listDocuments(params: DocumentListParams = {}): Promise<DocumentListResponse> {
    const response = await apiClient.get("/documents", {
      params: { ...(params.limit !== undefined ? { limit: params.limit } : {}), ...(params.offset !== undefined ? { offset: params.offset } : {}) },
    })
    return parseOrThrow(documentListSchema, response.data)
  },

  async getDocument(documentId: string): Promise<DocumentDetail> {
    const response = await apiClient.get(`/documents/${encodeURIComponent(documentId)}`)
    return parseOrThrow(documentDetailSchema, response.data)
  },

  async getDocumentStatus(documentId: string): Promise<DocumentStatusResponse> {
    const response = await apiClient.get(`/documents/${encodeURIComponent(documentId)}/status`)
    return parseOrThrow(documentStatusSchema, response.data)
  },

  async uploadDocument(
    file: File,
    metadata: UploadMetadataInput,
    options?: UploadTransferOptions,
  ): Promise<UploadAcceptedResponse> {
    const form = buildUploadFormData(file, metadata)
    const response = await apiClient.post("/documents/upload", form, {
      onUploadProgress: options?.onProgress
        ? (event) => {
            const percent = event.total === undefined || event.total === 0
              ? undefined
              : Math.round((event.loaded / event.total) * 100)
            if (percent !== undefined) {
              options.onProgress?.(percent)
            }
          }
        : undefined,
    })
    return parseOrThrow(uploadAcceptedSchema, response.data)
  },
}
