/**
 * Cross-cutting API response contracts mirrored from
 * `contracts/phase1/models.py` (canonical Phase 1 source of truth).
 * Field names and nullability match the backend exactly — do not rename.
 */

/** Literal union of error codes in `ErrorResponse`. */
export type ApiErrorCode =
  | "VALIDATION_ERROR"
  | "INVALID_FILE"
  | "FILE_TOO_LARGE"
  | "UNAUTHORIZED"
  | "FORBIDDEN"
  | "NOT_FOUND"
  | "CONFLICT"
  | "PROVIDER_UNAVAILABLE"
  | "INVALID_CITATIONS"
  | "INTERNAL_ERROR"

/**
 * Canonical error envelope returned by every client-visible failure,
 * including FastAPI validation errors. (`backend/app/api/errors.py`)
 */
export interface ApiErrorResponse {
  detail: string
  code: ApiErrorCode
  request_id: string
}
