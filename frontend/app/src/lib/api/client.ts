import axios, { AxiosError, type AxiosInstance, type RawAxiosResponseHeaders } from "axios"

import { env } from "@/lib/env"
import { apiErrorResponseSchema, HTTP_STATUS } from "@/lib/api/contracts"
import { ApiError } from "@/lib/api/error"

/**
 * Shared Axios client for every live KNEXUS call.
 *
 * - Base URL comes from `VITE_API_BASE_URL` (backend prefix `/api/v1` is
 *   appended per request — the same value the backend exposes as
 *   `API_V1_PREFIX`, never hardcoded beyond that segment).
 * - No identity of any kind is attached: Phase 1 identity is server-owned and
 *   the backend rejects identity-bearing fields outright.
 * - Failures leave this client as the normalized `ApiError`, preserving the
 *   HTTP status, canonical `code`, safe `detail` and `request_id` envelope.
 */

/** Resolves the backend base API origin of `/api/v1` requests. */
export function apiBase(): string {
  return `${env.apiBaseUrl}/api/v1`
}

/**
 * Reads `X-Request-ID` (case per transport) from a raw or AxiosHeaders
 * response header map, when present.
 */
function readRequestId(headers: RawAxiosResponseHeaders | undefined): string | undefined {
  if (headers === undefined) return undefined
  const candidates: unknown[] = []
  if (typeof headers === "object" && headers !== null) {
    candidates.push(headers["X-Request-ID"], headers["x-request-id"])
  }
  for (const candidate of candidates) {
    if (typeof candidate === "string" && candidate.length > 0) return candidate
  }
  return undefined
}

const DEFAULT_TIMEOUT_MS = 30_000

/** Normalizes a failed request into the contract-shaped `ApiError` chain.
 *  Exported so transport-failure tests exercise the exact production path. */
export function normalizeRejection(error: unknown): ApiError {
  if (error instanceof ApiError) return error

  const axiosError = axios.isAxiosError(error)
    ? error
    : new AxiosError(error instanceof Error ? error.message : "Request failed")
  const response = axiosError.response
  const status = response?.status
  const requestIdFromHeader = readRequestId(response?.headers)

  if (status !== undefined) {
    const envelope = apiErrorResponseSchema.safeParse(response?.data)
    if (envelope.success) {
      let code = envelope.data.code
      // Map HTTP status codes to canonical error codes
      if (status === HTTP_STATUS.PROVIDER_UNAVAILABLE) {
        code = "PROVIDER_UNAVAILABLE"
      }
      return new ApiError({
        status,
        code,
        detail: envelope.data.detail,
        requestId: envelope.data.request_id,
      })
    }
    // Server responded, but not with the contract shape. Keep the status for
    // diagnostics; the message must not leak raw response internals. The
    // correlation header is still surfaced when present.
    if (status >= 500) {
      return new ApiError({
        status,
        detail: "The backend could not complete the request. Try again later.",
        requestId: requestIdFromHeader,
      })
    }
    if (status === HTTP_STATUS.NOT_FOUND) {
      return new ApiError({
        status,
        detail: "The requested resource was not found.",
        requestId: requestIdFromHeader,
      })
    }
    if (status === HTTP_STATUS.FORBIDDEN) {
      return new ApiError({
        status,
        detail: "This action is not permitted.",
        requestId: requestIdFromHeader,
      })
    }
    return new ApiError({
      status,
      detail: "The backend returned an unexpected response.",
      requestId: requestIdFromHeader,
    })
  }

  // Transport-level failure (network loss, timeout, aborted).
  const code = axiosError.code
  if (code === "ECONNABORTED" || axiosError.message.includes("timeout")) {
    return new ApiError({
      detail: "The request timed out before the backend responded. Try again.",
    })
  }
  if (code === "ERR_NETWORK" || code === "NETWORK_ERROR") {
    return new ApiError({
      detail: "The backend could not be reached. Check that the KNEXUS backend is running.",
    })
  }
  return new ApiError({ detail: "The request could not be completed." })
}

function createApiClient(): AxiosInstance {
  const client = axios.create({
    baseURL: apiBase(),
    timeout: env.apiTimeoutMs ?? DEFAULT_TIMEOUT_MS,
    // Multipart uploads rely on the transport's own multipart Content-Type —
    // never set a default one here.
    headers: { Accept: "application/json" },
  })

  client.interceptors.response.use(
    // Successes pass through raw; services validate bodies against the
    // contract schemas at the boundary before anything reaches the UI.
    (response) => response,
    (error: unknown) => {
      // Normalize before Promise rejection so every consumer (TanStack Query,
      // hooks, handlers) observes one error type.
      throw normalizeRejection(error)
    },
  )

  return client
}

/** Instance shared by every API service (singleton: one runtime instance). */
export const apiClient: AxiosInstance = createApiClient()

/**
 * Build multipart FormData for the upload route: exactly one `file` field and
 * repeated `allowed_roles` fields (never a JSON/array serialization). Only
 * contract-defined metadata fields are included.
 */
export function buildUploadFormData(
  file: File,
  metadata: { allowed_roles: string[]; title?: string; description?: string },
): FormData {
  const form = new FormData()
  form.append("file", file, file.name)
  for (const role of metadata.allowed_roles) {
    form.append("allowed_roles", role)
  }
  if (metadata.title !== undefined) form.append("title", metadata.title)
  if (metadata.description !== undefined) form.append("description", metadata.description)
  return form
}
