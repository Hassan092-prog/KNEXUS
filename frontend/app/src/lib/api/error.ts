import {
  apiErrorResponseSchema,
  API_ERROR_CODES,
  type ApiErrorCode,
  HTTP_STATUS,
} from "@/lib/api/contracts"

/**
 * Normalized, display-safe error information. `detail` is always a message
 * suitable for rendering (backend safe detail or a neutral fallback); no
 * exception text, stack traces, or internal provider information is exposed.
 */
export interface NormalizedApiError {
  /** HTTP status when a response was received; undefined for transport failures. */
  status?: number
  /** Canonical backend error code, when one was returned. */
  code?: ApiErrorCode
  detail: string
  /** Server correlation UUID (`request_id` / `X-Request-ID`) when available. */
  requestId?: string
}

/**
 * Error carrying the backend's canonical envelope. Every failure mode reaches
 * the UI as this instance (live: from the Axios interceptor; mock: thrown by
 * handlers), so feature code and `ErrorState` only ever see one error shape.
 */
export class ApiError extends Error {
  readonly status?: number
  readonly code?: ApiErrorCode
  readonly detail: string
  readonly requestId?: string

  constructor({ status, code, detail, requestId }: NormalizedApiError) {
    super(detail)
    this.name = "ApiError"
    this.status = status
    this.code = code
    this.detail = detail
    this.requestId = requestId
  }
}

/**
 * Mock-layer failure. Built from a contract-shaped envelope so mock responses
 * exercise the exact display path that live errors take.
 */
export class MockApiError extends ApiError {
  constructor(
    envelope: { detail: string; code: ApiErrorCode; request_id: string },
    status: number,
  ) {
    super({
      status,
      code: envelope.code,
      detail: envelope.detail,
      requestId: envelope.request_id,
    })
    this.name = "MockApiError"
  }
}

/** Transport failure message keyed by the Axios failure signature. */
function transportDetail(code: string | undefined, message: string): string {
  if (code === "ERR_NETWORK" || code === "NETWORK_ERROR") {
    return "The backend could not be reached. Check that the KNEXUS backend is running."
  }
  if (code === "ECONNABORTED") {
    return "The request timed out before the backend responded. Try again."
  }
  if (code === "ECONNREFUSED") {
    return "The connection to the backend was refused."
  }
  return message
}

/**
 * Normalize any thrown value into a display-safe `NormalizedApiError`.
 *
 * Order of resolution:
 * 1. `ApiError`/`MockApiError` (already normalized; mock handlers throw these).
 * 2. Axios/HTTP-like error with `error.response` — extract status, code, detail,
 *    and request_id from the response data envelope.
 * 3. Transport-level failures (network loss, timeout) — no status.
 * 4. Contract shape violations that already preserved the HTTP status.
 * 5. Anything else → neutral fallback, never exception internals.
 */
export function toApiError(error: unknown): NormalizedApiError {
  if (error instanceof ApiError) {
    return { status: error.status, code: error.code, detail: error.detail, requestId: error.requestId }
  }

  if (error instanceof Error) {
    // Error with possible Axios response attachment, or with custom status/code
     // properties thrown by the client interceptor or mock handlers.
     const candidate = error as Error & {
       code?: string | undefined
       status?: number | undefined
       response?: unknown
       toJSON?: () => unknown
     }

    // Axios error with a response (HTTP error from the backend).
    if (candidate.response !== undefined) {
      const axiosError = candidate as Error & {
        response: { status?: number; data?: unknown; statusText?: string; headers: unknown }
        code?: string
      }
      const response = axiosError.response
      if (typeof response?.status === "number" && response.status !== 0) {
        const envelope = apiErrorResponseSchema.safeParse(response.data)
        if (envelope.success) {
          return {
            status: response.status,
            code: envelope.data.code,
            detail: envelope.data.detail,
            requestId: envelope.data.request_id,
          }
        }
        // Response received but body doesn't match the contract shape.
        if (response.status >= 500) {
          return {
            status: response.status,
            detail: "The backend could not complete the request. Try again later.",
          }
        }
        if (response.status === HTTP_STATUS.NOT_FOUND) {
          return {
            status: response.status,
            detail: "The requested resource was not found.",
          }
        }
        if (response.status === HTTP_STATUS.FORBIDDEN) {
          return {
            status: response.status,
            detail: "This action is not permitted.",
          }
        }
        return {
          status: response.status,
          detail: transportDetail(
            axiosError.code,
            "The backend returned an unexpected response.",
          ),
        }
      }
      // Status is not a valid number; treat as transport failure.
      return {
        detail: transportDetail(axiosError.code, "The request could not be completed."),
      }
    }

    // Non-Axios Error instance — check for a status property like a
    // manually-thrown ApiError shape, then fall back to transport detail.
    if (typeof candidate.status === "number" && candidate.status !== 0) {
      const response = apiErrorResponseSchema.safeParse(candidate.toJSON?.())
      if (response.success) {
        return {
          status: candidate.status,
          code: response.data.code,
          detail: response.data.detail,
          requestId: response.data.request_id,
        }
      }
      return {
        status: candidate.status,
        detail: transportDetail(candidate.code, "The backend returned an unexpected response."),
      }
    }

    return {
      detail: transportDetail(candidate.code, "The request could not be completed."),
    }
  }

  return { detail: "The request could not be completed." }
}

/** True when the failure means "unavailable", used to influence retry UI copy. */
export function isProviderErrorCode(code: string | undefined): boolean {
  return code === "PROVIDER_UNAVAILABLE"
}

export const isKnownErrorCode = (code: string | undefined): code is ApiErrorCode =>
  typeof code === "string" && (API_ERROR_CODES as readonly string[]).includes(code)
