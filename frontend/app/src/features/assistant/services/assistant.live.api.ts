import { apiClient } from "@/lib/api/client"
import { queryRequestSchema, queryResponseSchema } from "@/lib/api/contracts"
import type { QueryRequest, QueryResponse } from "@/features/assistant/types/assistant.types"
import { parseOrThrow } from "@/features/documents/services/document.live.api"

/**
 * Live implementation of the AssistantApi against `POST /api/v1/query`.
 * One-shot and non-streaming: `stream: false` is always sent, and the
 * contract schema (which rejects `stream: true`) gates the payload.
 */
export const assistantLiveApi = {
  async submitQuery(payload: QueryRequest): Promise<QueryResponse> {
    const request = queryRequestSchema.parse({ ...payload, stream: false })
    const response = await apiClient.post(
      "/query",
      { question: request.question, top_k: request.top_k, stream: false },
      { headers: { "Content-Type": "application/json" } },
    )
    return parseOrThrow(queryResponseSchema, response.data)
  },
}
