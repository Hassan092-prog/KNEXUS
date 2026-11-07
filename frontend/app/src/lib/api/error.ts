export interface NormalizedApiError { code?: string; detail?: string; requestId?: string }
export function toApiError(error: unknown): NormalizedApiError {
  return { detail: error instanceof Error ? error.message : "Request failed" }
}
