import type { QueryRequest, QueryResponse } from "@/features/assistant/types/assistant.types"

/**
 * Shared assistant service interface (Z02 boundary). Phase 1 is one-shot and
 * non-streaming; implementations must always send `stream: false`.
 */
export interface AssistantApi {
  submitQuery(payload: QueryRequest): Promise<QueryResponse>
}
