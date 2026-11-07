import { describe, expect, it } from "vitest"
import type { ApiErrorCode } from "@/lib/api/contracts"
import { AxiosError, AxiosHeaders } from "axios"

import { ApiError, MockApiError, isProviderErrorCode, toApiError } from "@/lib/api/error"
import { normalizeRejection } from "@/lib/api/client"

/**
 * Error normalization tests: the canonical `{detail, code, request_id}`
 * envelope, non-contract successes/failures, transport failures (network,
 * timeout), and identity-free display messages.
 */

const ENVELOPE = {
  detail: "The upload exceeds 10 MiB.",
  code: "FILE_TOO_LARGE" as ApiErrorCode,
  request_id: "00000000-0000-4000-8000-000000000abc",
}

function axiosRejection(status: number, data: unknown, headers: Record<string, string> = { "x-request-id": ENVELOPE.request_id }): AxiosError {
  const config = { headers: new AxiosHeaders() }
  return new AxiosError("Request failed", "ERR_BAD_REQUEST", config, { headers: new AxiosHeaders() } as never, {
    status,
    statusText: "Response",
    data,
    headers: AxiosHeaders.from(headers),
    config,
  } as never)
}

describe("toApiError", () => {
  it("passes ApiError instances through untouched", () => {
    const error = new ApiError({ status: 403, code: "FORBIDDEN", detail: "denied", requestId: ENVELOPE.request_id })
    expect(toApiError(error)).toEqual({ status: 403, code: "FORBIDDEN", detail: "denied", requestId: ENVELOPE.request_id })
  })

  it("keeps the HTTP status and canonical code from an envelope response", () => {
    const error = axiosRejection(413, ENVELOPE)
    const normalized = toApiError(error)
    expect(normalized.status).toBe(413)
    expect(normalized.code).toBe("FILE_TOO_LARGE")
    expect(normalized.detail).toBe(ENVELOPE.detail)
    expect(normalized.requestId).toBe(ENVELOPE.request_id)
  })

  it("never leaks raw response internals for non-contract responses", () => {
    const error = axiosRejection(500, { stack: "secret-internal-trace" })
    const normalized = toApiError(error)
    expect(normalized.status).toBe(500)
    expect(normalized.detail).not.toContain("secret-internal-trace")
    expect(normalized.detail).toBe("The backend could not complete the request. Try again later.")
  })

  it("offers a neutral 404/403 message when the envelope is missing", () => {
    expect(toApiError(axiosRejection(404, "<html>boom</html>")).detail).toBe(
      "The requested resource was not found.",
    )
    expect(toApiError(axiosRejection(403, "<html>boom</html>")).detail).toBe(
      "This action is not permitted.",
    )
  })

  it("maps network loss and timeouts to safe transport copy without a status", () => {
    const network = new AxiosError("Network Error", "ERR_NETWORK")
    const timeout = new AxiosError("timeout of 30s exceeded", "ECONNABORTED")
    for (const failure of [network, timeout]) {
      const normalized = toApiError(failure)
      expect(normalized.status).toBeUndefined()
      expect(normalized.detail).toMatch(/backend/)
      expect(normalized.detail).toBe(toApiError(failure).detail)
    }
  })

  it("falls back to a neutral message for unknown throwables", () => {
    expect(toApiError(new Error("raw")).detail).toBe("The request could not be completed.")
    expect(toApiError("fail-forever").detail).toBe("The request could not be completed.")
    expect(toApiError(undefined).detail).toBe("The request could not be completed.")
  })
})

describe("normalizeRejection (client interceptor path)", () => {
  it("preserves status codes and the request_id envelope", () => {
    const result = normalizeRejection(axiosRejection(503, ENVELOPE))
    expect(result).toBeInstanceOf(ApiError)
    expect(result.status).toBe(503)
    expect(result.code).toBe("PROVIDER_UNAVAILABLE")
    expect(result.requestId).toBe(ENVELOPE.request_id)
  })

  it("falls back to the X-Request-ID header when the body is not contract-shaped", () => {
    const result = normalizeRejection(axiosRejection(502, { oops: true }))
    expect(result.code).toBeUndefined()
    expect(result.requestId).toBe(ENVELOPE.request_id)
    expect(result.status).toBe(502)
  })

  it("rewraps already-normalized ApiErrors untouched (mock path)", () => {
    const original = new ApiError({ status: 422, code: "VALIDATION_ERROR", detail: "no" })
    expect(normalizeRejection(original)).toBe(original)
  })
})

describe("mock error envelope", () => {
  it("builds contract-shaped MockApiError", () => {
    const mockError = new MockApiError(ENVELOPE, 413)
    expect(mockError.name).toBe("MockApiError")
    expect(mockError.status).toBe(413)
    expect(mockError.code).toBe("FILE_TOO_LARGE")
    expect(mockError.detail).toBe(ENVELOPE.detail)
    expect(toApiError(mockError).code).toBe("FILE_TOO_LARGE")
  })
})

describe("isProviderErrorCode", () => {
  it("recognizes provider unavailability only", () => {
    expect(isProviderErrorCode("PROVIDER_UNAVAILABLE")).toBe(true)
    expect(isProviderErrorCode("INTERNAL_ERROR")).toBe(false)
    expect(isProviderErrorCode(undefined)).toBe(false)
  })
})
