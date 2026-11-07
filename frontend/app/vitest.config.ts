import path from 'node:path'
import { defineConfig } from 'vitest/config'

/**
 * Vitest runs the full suite in the jsdom environment:
 * - service/API tests (mock mode, live parsing, error normalization)
 * - component tests (document library, upload, detail, assistant, shared)
 *
 * `environmentMatchGlobs` would split environments, but the component tests
 * and service tests share the same client code, so jsdom globally is simpler
 * and still fast. Mode/delay environment values are pinned for determinism.
 */
export default defineConfig({
  resolve: {
    alias: {
      '@': path.resolve(import.meta.dirname, 'src'),
    },
  },
  test: {
    environment: 'jsdom',
    include: ['src/**/*.test.{ts,tsx}'],
    setupFiles: ['src/test/setup.ts'],
    globals: true,
    // One shot, no watch: `npm run test` is the CI gate.
    restoreMocks: true,
  },
  define: {
    'import.meta.env.VITE_DATA_MODE': '"mock"',
    'import.meta.env.VITE_MOCK_DELAY_MS': '"0"',
    'import.meta.env.DEV': 'false',
    'import.meta.env.PROD': 'true',
  },
})
