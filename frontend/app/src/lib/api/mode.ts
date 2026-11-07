import { env } from "@/lib/env"

/** Active data mode: mock fixtures or the live KNEXUS backend. */
export type DataMode = "mock" | "live"

/**
 * Resolve the configured data mode. "mock" whenever `VITE_DATA_MODE` is not
 * exactly "live" — a live backend connection must always be explicit.
 */
export function getDataMode(): DataMode {
  return env.dataMode === "live" ? "live" : "mock"
}

/**
 * Artificial delay applied to mock-mode responses (exercises loading states).
 * Tests pin `VITE_MOCK_DELAY_MS=0`. Ignored in live mode.
 */
export function mockDelay(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, env.mockDelayMs))
}
