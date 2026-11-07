import { describe, expect, it } from "vitest"

import {
  apiErrorResponseSchema,
  citationSchema,
  documentDetailSchema,
  documentListSchema,
  documentStatusSchema,
  HTTP_STATUS,
  queryRequestSchema,
  queryResponseSchema,
  uploadAcceptedSchema,
  uploadMetadataSchema,
} from "@/lib/api/contracts"

import documentDetailRaw from "@/mocks/data/document-detail.json"
import documentListRaw from "@/mocks/data/document-list.json"
import documentStatusCompleteRaw from "@/mocks/data/document-status-complete.json"
import documentStatusFailedRaw from "@/mocks/data/document-status-failed.json"
import documentStatusProcessingRaw from "@/mocks/data/document-status-processing.json"
import documentStatusQueuedRaw from "@/mocks/data/document-status-queued.json"
import providerErrorRaw from "@/mocks/data/provider-error.json"
import queryAbstentionRaw from "@/mocks/data/query-abstention.json"
import queryAnswerRaw from "@/mocks/data/query-answer.json"
import queryRequestRaw from "@/mocks/data/query-request.json"
import uploadAcceptedRaw from "@/mocks/data/upload-accepted.json"
import uploadMetadataRaw from "@/mocks/data/upload-metadata.json"
import validationErrorRaw from "@/mocks/data/validation-error.json"

/**
 * Contract validation tests: canonical fixtures parse, cross-field invariants
 * hold, and contract violations are rejected instead of silently coerced.
 */
describe("contract schemas: canonical fixtures", () => {
  it.each([
    ["document-detail", documentDetailRaw, documentDetailSchema],
    ["document-list", documentListRaw, documentListSchema],
    ["status-queued", documentStatusQueuedRaw, documentStatusSchema],
    ["status-processing", documentStatusProcessingRaw, documentStatusSchema],
    ["status-complete", documentStatusCompleteRaw, documentStatusSchema],
    ["status-failed", documentStatusFailedRaw, documentStatusSchema],
    ["query-answer", queryAnswerRaw, queryResponseSchema],
    ["query-abstention", queryAbstentionRaw, queryResponseSchema],
    ["query-request", queryRequestRaw, queryRequestSchema],
    ["upload-metadata", uploadMetadataRaw, uploadMetadataSchema],
    ["upload-accepted", uploadAcceptedRaw, uploadAcceptedSchema],
    ["error-provider", providerErrorRaw, apiErrorResponseSchema],
    ["error-validation", validationErrorRaw, apiErrorResponseSchema],
  ])("%s parses", (_name, raw, schema) => {
    expect(schema.safeParse(raw).success).toBe(true)
  })
})

describe("contract schemas: invariants", () => {
  it("rejects stream=true requests (Phase 1 accepts false only)", () => {
    const rejected = queryRequestSchema.safeParse({ question: "ok", stream: true })
    expect(rejected.success).toBe(false)
  })

  it("applies the backend defaults for top_k and stream", () => {
    const parsed = queryRequestSchema.parse({ question: "What is the leave policy?" })
    expect(parsed).toEqual({ question: "What is the leave policy?", top_k: 5, stream: false })
  })

  it("rejects an answer whose inline markers do not match citation IDs", () => {
    const broken = {
      ...queryAnswerRaw,
      answer: "An answer with a stale marker [7].",
    }
    expect(queryResponseSchema.safeParse(broken).success).toBe(false)
  })

  it("rejects an abstention with a non-null answer", () => {
    const broken = {
      ...queryAbstentionRaw,
      answer: "an answer leaked",
    }
    expect(queryResponseSchema.safeParse(broken).success).toBe(false)
  })

  it("rejects conflict responses where citation ids repeat", () => {
    const citations = [
      citationSchema.parse((queryAnswerRaw.citations as Array<Record<string, unknown>>)[0]),
      citationSchema.parse((queryAnswerRaw.citations as Array<Record<string, unknown>>)[0]),
    ]
    const broken = {
      ...queryAnswerRaw,
      answer: `${String(queryAnswerRaw.answer)} [2]`,
      citations,
    }
    expect(queryResponseSchema.safeParse(broken).success).toBe(false)
  })

  it("rejects unknown fields (backend uses extra='forbid')", () => {
    const broken = { ...uploadAcceptedRaw, sneaky: "field" }
    expect(uploadAcceptedSchema.safeParse(broken).success).toBe(false)
  })

  it("rejects duplicate upload roles", () => {
    expect(
      uploadMetadataSchema.safeParse({ allowed_roles: ["employee", "employee"] }).success,
    ).toBe(false)
  })

  it("rejects roles outside the canonical enum", () => {
    expect(uploadMetadataSchema.safeParse({ allowed_roles: ["admin"] }).success).toBe(false)
  })

  it("rejects a failed status without failure details", () => {
    const broken = { ...documentStatusFailedRaw, failure_code: null }
    expect(documentStatusSchema.safeParse(broken).success).toBe(false)
  })

  it("rejects a complete status with incomplete chunks", () => {
    const broken = { ...documentStatusCompleteRaw, chunks_processed: 0 }
    expect(documentStatusSchema.safeParse(broken).success).toBe(false)
  })

  it("rejects list pages exceeding their limit meta", () => {
    const list = documentListSchema.parse(documentListRaw)
    const broken = { ...list, data: [list.data[0], list.data[1], list.data[2]] }
    const limited = { ...broken, meta: { ...broken.meta, limit: 2 } }
    expect(documentListSchema.safeParse(limited).success).toBe(false)
  })

  it("keeps the canonical HTTP status map in one place", () => {
    expect(HTTP_STATUS.TOO_LARGE).toBe(413)
    expect(HTTP_STATUS.VALIDATION).toBe(422)
    expect(HTTP_STATUS.PROVIDER_UNAVAILABLE).toBe(503)
  })
})
