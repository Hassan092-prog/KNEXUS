/**
 * Frontend environment configuration. No secrets belong here — the backend
 * owns all provider credentials (Phase 1 security model). Mirrors
 * `frontend/app/.env.example`.
 */
export const env = {
  /** Base URL of the KNEXUS backend, without trailing slash. */
  apiBaseUrl: stripTrailingSlash(import.meta.env.VITE_API_BASE_URL) ?? "http://localhost:8000",
  /** Axios timeout override in milliseconds. */
  apiTimeoutMs: parseTimeout(import.meta.env.VITE_API_TIMEOUT_MS),
  /** API mode: "mock" serves fixture-backed responses, "live" the backend. */
  dataMode: import.meta.env.VITE_DATA_MODE === "live" ? "live" : "mock",
  /** Artificial delay applied to mock-mode responses. */
  mockDelayMs: parseTimeout(import.meta.env.VITE_MOCK_DELAY_MS) ?? 0,
} as const

function parseTimeout(value: string | undefined): number | undefined {
  if (value === undefined || value === "") return undefined
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 && Number.isInteger(parsed) ? parsed : undefined
}

function stripTrailingSlash(value: string | undefined): string | undefined {
  if (value === undefined) return undefined
  return value.length > 1 && value.endsWith("/") ? value.slice(0, -1) : value
}
