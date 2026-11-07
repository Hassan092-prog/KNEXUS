import type { QueryRequest, QueryResponse } from "@/features/assistant/types/assistant.types"
import { randomUuid } from "@/lib/utils/random"

import { mockDelay } from "@/lib/api/mode"
import { MockApiError } from "@/lib/api/error"
import {
  CANONICAL_QUERY_ABSTENTION,
  CANONICAL_QUERY_ANSWER,
  questionTriggersAbstention,
  questionTriggersNetworkFailure,
  questionTriggersProviderError,
} from "@/mocks/store"

/**
 * Mock handlers for the assistant feature operation.
 *
 * - Default: canonical `query-answer.json` with citations.
 * - Absence keywords → canonical `query-abstention.json`.
 * - "provider unavailable" → canonical `provider-error.json` envelope (503).
 * - "network failure" → transport-level error for the error pipeline.
 *
 * The keyword triggers are a documented front-end testing aid: the real
 * backend abstains on retrieval evidence, not keywords. Only word choices
 * used as deliberate triggers here; no inference about backend logic.
 */

export const assistantHandlers = {
  async submitQuery(payload: QueryRequest): Promise<QueryResponse> {
    await mockDelay()

    const question = payload.question
    if (questionTriggersNetworkFailure(question)) {
      const transportError = new Error("Network Error")
      ;(transportError as Error & { code?: string }).code = "ERR_NETWORK"
      throw transportError
    }

    if (questionTriggersProviderError(question)) {
      throw new MockApiError(
        {
          detail: "The local model service is unavailable.",
          code: "PROVIDER_UNAVAILABLE",
          request_id: randomUuid(),
        },
        503,
      )
    }

    if (questionTriggersAbstention(question)) {
      return { ...CANONICAL_QUERY_ABSTENTION }
    }

    return { ...CANONICAL_QUERY_ANSWER }
  },
}
