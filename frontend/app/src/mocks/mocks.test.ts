import { beforeEach, describe, expect, it } from "vitest"

import { documentHandlers } from "@/mocks/handlers/documents"
import { assistantHandlers } from "@/mocks/handlers/assistant"
import { documentListSchema, documentStatusSchema, uploadMetadataSchema } from "@/lib/api/contracts"
import { MockApiError } from "@/lib/api/error"
import { resetMockStore } from "@/mocks/store"

const FILE = (name: string, size = 4096) =>
  new File([new Uint8Array(size)], name, { type: name.endsWith(".docx") ? "application/vnd.openxmlformats-officedocument.wordprocessingml.document" : "application/pdf" })

/**
 * Mock mode behavior tests: deterministic, in-memory only, and driven by the
 * same canonical fixtures/contract schemas as live mode.
 */
beforeEach(() => {
  resetMockStore()
})

describe("documentHandlers.listDocuments", () => {
  it("pages with limit/offset meta and contract-valid data", async () => {
    const page = await documentHandlers.listDocuments({ limit: 2, offset: 2 })
    expect(() => {
      documentListSchema.parse({ data: page.data, meta: page.meta })
    }).not.toThrow()
    expect(page.data).toHaveLength(2)
    expect(page.meta).toEqual({ total: 6, limit: 2, offset: 2 })
  })

  it("sorts newest-first (matches the backend ordering)", async () => {
    const page = await documentHandlers.listDocuments({ limit: 10 })
    const dates = page.data.map((document) => document.created_at)
    expect([...dates].sort().reverse()).toEqual(dates)
  })
})

describe("documentHandlers.uploadDocument", () => {
  it("accepts a contract-valid upload and registers the document queued", async () => {
    const accepted = await documentHandlers.uploadDocument(FILE("policy.pdf"), {
      allowed_roles: ["employee"],
      title: "Policy",
    })
    const list = await documentHandlers.listDocuments()
    expect(list.meta.total).toBe(7)
    const uploaded = list.data.find((document) => document.id === accepted.document_id)
    expect(uploaded?.status).toBe("queued")
    expect(uploaded?.title).toBe("Policy")
  })

  it("rejects empty role selection with the canonical validation envelope", async () => {
    await expect(
      documentHandlers.uploadDocument(FILE("policy.pdf"), { allowed_roles: [] }),
    ).rejects.toMatchObject({ code: "VALIDATION_ERROR", status: 422 })
  })

  it("rejects contract-breaking metadata before storing anything", async () => {
    expect(uploadMetadataSchema.safeParse({ allowed_roles: ["employee", "employee"] }).success).toBe(false)
    await expect(
      documentHandlers.uploadDocument(FILE("policy.pdf"), {
        allowed_roles: ["employee", "employee"],
      }),
    ).rejects.toBeInstanceOf(MockApiError)
  })
})

describe("documentHandlers.getDocumentStatus (processing lifecycle)", () => {
  it("advances queued -> processing -> complete across polls", async () => {
    const accepted = await documentHandlers.uploadDocument(FILE("handbook.pdf", 10240), {
      allowed_roles: ["employee"],
    })
    const documentId = accepted.document_id

    const first = await documentHandlers.getDocumentStatus(documentId)
    expect(first.status).toBe("queued")
    expect(first.progress_percent).toBeNull()

    const second = await documentHandlers.getDocumentStatus(documentId)
    expect(second.status).toBe("processing")
    expect(second.total_chunks).not.toBeNull()
    expect(second.failure_code).toBeNull()

    const third = await documentHandlers.getDocumentStatus(documentId)
    expect(third.status).toBe("complete")
    expect(third.progress_percent).toBe(100)
    expect(third.chunks_processed).toBe(third.total_chunks)
    for (const stage of [first, second, third]) {
      expect(() => documentStatusSchema.parse(stage)).not.toThrow()
    }
  })

  it("stays terminal once complete", async () => {
    const accepted = await documentHandlers.uploadDocument(FILE("doc.pdf"), {
      allowed_roles: ["manager"],
    })
    for (let poll = 0; poll < 4; poll += 1) {
      await documentHandlers.getDocumentStatus(accepted.document_id)
    }
    const status = await documentHandlers.getDocumentStatus(accepted.document_id)
    expect(status.status).toBe("complete")
  })

  it("surfaces the canonical failed ingestion shape for the failure marker", async () => {
    const accepted = await documentHandlers.uploadDocument(FILE("will-fail.pdf"), {
      allowed_roles: ["employee"],
    })
    const status = await documentHandlers.getDocumentStatus(accepted.document_id)
    expect(status.status).toBe("failed")
    expect(status.failure_code).toBe("INVALID_FILE")
    expect(status.failure_message).not.toBeNull()
    expect(() => documentStatusSchema.parse(status)).not.toThrow()
  })

  it("throws the canonical NOT_FOUND envelope for unknown ids", async () => {
    await expect(documentHandlers.getDocumentStatus("00000000-0000-4000-8000-0000000000ff")).rejects.toMatchObject({
      code: "NOT_FOUND",
      status: 404,
    })
  })
})

describe("assistantHandlers", () => {
  it("answers with citations that match inline markers", async () => {
    const response = await assistantHandlers.submitQuery({ question: "How much annual leave do I have?", top_k: 5 })
    expect(response.abstained).toBe(false)
    expect(response.citations.length).toBeGreaterThan(0)
    expect(response.meta.model).not.toBe("")
  })

  it("abstains on the documented keyword trigger (HTTP-200 semantics)", async () => {
    const response = await assistantHandlers.submitQuery({ question: "something entirely unrelated", top_k: 5, stream: false })
    expect(response.abstained).toBe(true)
    expect(response.answer).toBeNull()
    expect(response.citations).toEqual([])
    expect(response.abstention_reason).not.toBeNull()
  })

  it("serves the canonical PROVIDER_UNAVAILABLE envelope on trigger", async () => {
    await expect(
      assistantHandlers.submitQuery({ question: "give me things the provider says unavailable now" }),
    ).rejects.toMatchObject({ code: "PROVIDER_UNAVAILABLE", status: 503 })
  })

  it("raises a transport-level network failure on trigger", async () => {
    await expect(
      assistantHandlers.submitQuery({ question: "trigger the network failure companion tool" }),
    ).rejects.toMatchObject({ code: "ERR_NETWORK" })
  })
})
