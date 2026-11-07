import type { DocumentApi, UploadTransferOptions } from "@/features/documents/services/document.api"
import type { AssistantApi } from "@/features/assistant/services/assistant.api"
import type {
  DocumentDetail,
  DocumentListParams,
  DocumentListResponse,
  DocumentStatusResponse,
  UploadAcceptedResponse,
  UploadMetadataInput,
} from "@/features/documents/types/document.types"
import type { QueryRequest, QueryResponse } from "@/features/assistant/types/assistant.types"

import {
  documentDetailSchema,
  documentListSchema,
  documentStatusSchema,
  queryResponseSchema,
  uploadAcceptedSchema,
} from "@/lib/api/contracts"
import { documentHandlers } from "@/mocks/handlers/documents"
import { assistantHandlers } from "@/mocks/handlers/assistant"

/**
 * Central mock adapter/dispatcher.
 *
 * Each handler returns contract-shaped data; every response is re-parsed
 * through the same Zod schemas that gate live responses before it leaves the
 * mock layer. Combined with `store.ts` parsing fixtures at import time, the
 * mock can never emit a shape the backend contract does not define.
 */

function validateDetail(data: unknown): DocumentDetail {
  return documentDetailSchema.parse(data)
}

function validateList(data: unknown): DocumentListResponse {
  return documentListSchema.parse(data)
}

function validateStatus(data: unknown): DocumentStatusResponse {
  return documentStatusSchema.parse(data)
}

function validateUploadAccepted(data: unknown): UploadAcceptedResponse {
  return uploadAcceptedSchema.parse(data)
}

function validateQuery(data: unknown): QueryResponse {
  return queryResponseSchema.parse(data)
}

/** Creates the mock DocumentApi with Zod re-validation at every boundary. */
export function createMockDocumentApi(): DocumentApi {
  return {
    async listDocuments(params: DocumentListParams = {}): Promise<DocumentListResponse> {
      const response = await documentHandlers.listDocuments(params)
      return validateList(response)
    },

    async getDocument(documentId: string): Promise<DocumentDetail> {
      return validateDetail(await documentHandlers.getDocument(documentId))
    },

    async getDocumentStatus(documentId: string): Promise<DocumentStatusResponse> {
      return validateStatus(await documentHandlers.getDocumentStatus(documentId))
    },

    async uploadDocument(
      file: File,
      metadata: UploadMetadataInput,
      _options?: UploadTransferOptions,
    ): Promise<UploadAcceptedResponse> {
      return validateUploadAccepted(await documentHandlers.uploadDocument(file, metadata))
    },
  }
}

/** Creates the mock AssistantApi with Zod re-validation at the boundary. */
export function createMockAssistantApi(): AssistantApi {
  return {
    async submitQuery(payload: QueryRequest): Promise<QueryResponse> {
      return validateQuery(await assistantHandlers.submitQuery(payload))
    },
  }
}
