import { getDataMode, type DataMode } from "@/lib/api/mode"
import type { DocumentApi } from "@/features/documents/services/document.api"
import type { AssistantApi } from "@/features/assistant/services/assistant.api"
import { documentLiveApi } from "@/features/documents/services/document.live.api"
import { assistantLiveApi } from "@/features/assistant/services/assistant.live.api"
import { createMockDocumentApi, createMockAssistantApi } from "@/mocks/mock-server"

/**
 * Service factory: consumers bind to the `DocumentApi`/`AssistantApi`
 * interfaces only. Whether the backing implementation is the live KNEXUS
 * endpoint or the canonical-fixture mock is decided here from
 * `VITE_DATA_MODE` — nothing else in the app branches on the mode.
 */

let mockDocumentApi: DocumentApi | undefined
let mockAssistantApi: AssistantApi | undefined

function selectDocumentApi(): DocumentApi {
  const mode = getDataMode()
  if (mode === "live") return documentLiveApi
  mockDocumentApi ??= createMockDocumentApi()
  return mockDocumentApi
}

function selectAssistantApi(): AssistantApi {
  const mode = getDataMode()
  if (mode === "live") return assistantLiveApi
  mockAssistantApi ??= createMockAssistantApi()
  return mockAssistantApi
}

export function getDocumentApi(mode?: DataMode): DocumentApi {
  if (mode === "live") return documentLiveApi
  return selectDocumentApi()
}

export function getAssistantApi(mode?: DataMode): AssistantApi {
  if (mode === "live") return assistantLiveApi
  return selectAssistantApi()
}

export const isMockMode = (): boolean => getDocumentApi() !== documentLiveApi

export { getDataMode }
export type { DataMode }
