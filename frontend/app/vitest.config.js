import path from 'node:path';
import { defineConfig } from 'vitest/config';
// Vitest runs service-level tests (mock mode, live parsing, error
// normalization) in a plain node environment — no browser or component tests
// are needed for Z02.
export default defineConfig({
    resolve: {
        alias: {
            '@': path.resolve(import.meta.dirname, "src"),
        },
    },
    test: {
        environment: 'node',
        include: ['src/**/*.test.{ts,tsx}'],
    },
    define: {
        'import.meta.env.VITE_DATA_MODE': '"mock"',
        'import.meta.env.VITE_MOCK_DELAY_MS': '"0"',
        'import.meta.env.DEV': 'false',
        'import.meta.env.PROD': 'true',
    },
});
