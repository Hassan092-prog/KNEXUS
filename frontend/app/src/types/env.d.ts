/// <reference types="vite/client" />

/**
 * Environment variables consumed by the frontend.
 * See frontend/app/.env.example. No secrets live here — the backend
 * owns all provider credentials (Phase 1 security model).
 */
interface ImportMetaEnv {
  /** Base URL of the KNEXUS backend, without trailing slash. */
  readonly VITE_API_BASE_URL?: string
  /** Optional Axios timeout override in milliseconds. */
  readonly VITE_API_TIMEOUT_MS?: string
}
