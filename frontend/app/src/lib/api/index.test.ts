import { describe, expect, it } from "vitest"

import { getAssistantApi, getDocumentApi, isMockMode, getDataMode } from "@/lib/api"
import { documentLiveApi } from "@/features/documents/services/document.live.api"
import { assistantLiveApi } from "@/features/assistant/services/assistant.live.api"
import { documentHandlers } from "@/mocks/handlers/documents"

/**
 * Service-factory tests: mock and live implementations share one interface
 * and the mode decides which one consumers receive. In the test environment
 * `VITE_DATA_MODE` is pinned to `mock`.
 */
describe("data mode", () => {
  it("resolves mock mode in the pinned test environment", () => {
    expect(getDataMode()).toBe("mock")
    expect(isMockMode()).toBe(true)
  })
})

describe("getDocumentApi", () => {
  it("returns the mock implementation by default", async () => {
    const api = getDocumentApi()
    const response = await api.listDocuments({ limit: 2 })

    expect(response.meta.total).toBeGreaterThan(0)
    expect(response.data.length).toBeLessThanOrEqual(2)
    // Contract-guaranteed fields, nothing invented:
    for (const summary of response.data) {
      expect(Object.keys(summary).sort()).toEqual(
        ["allowed_roles", "chunk_count", "created_at", "id", "source_type", "status", "title"].sort(),
      )
    }
  })

  it("returns the singleton mock across calls", () => {
    expect(getDocumentApi()).toBe(getDocumentApi())
  })

  it("can force the live implementation explicitly", () => {
    expect(getDocumentApi("live")).toBe(documentLiveApi)
    expect(getDocumentApi("live")).not.toBe(documentHandlers)
  })
})

describe("getAssistantApi", () => {
  it("returns the mock assistant by default and live when forced", async () => {
    const api = getAssistantApi()
    const response = await api.submitQuery({ question: "What is the leave policy?", top_k: 5, stream: false })
    expect(response.abstained).toBe(false)
    expect(response.citations.length).toBeGreaterThan(0)

    expect(getAssistantApi("live")).toBe(assistantLiveApi)
  })
})
