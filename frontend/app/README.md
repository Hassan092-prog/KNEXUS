# KNEXUS frontend app

Vite + React 19 + TypeScript + Tailwind CSS v4 single-page app for the KNEXUS backend.
See the phase-by-phase instructions in [../README.md](../README.md).

## Scripts

Run from this directory (`frontend/app`):

| Command | Purpose |
|---|---|
| `npm run dev` | Development server on `http://localhost:5173` (port allowed by backend CORS) |
| `npm run build` | Type-check then production build into `dist/` |
| `npm run typecheck` | TypeScript project check (`tsc -b`) |
| `npm run test` | Vitest suite (mock mode, live parsing, error normalization) |
| `npm run lint` | Oxlint source checks |
| `npm run preview` | Preview the production build |

## Verified (5 November 2026)

- `npm run typecheck` (strict), `npm run test` (35 tests), `npm run build`, `npm run lint`
  pass clean on Node 22.
- Mock and live modes verified in the rendered DOM via headless Chrome on the production
  build — see `../docs/PHASE_2_CHANGELOG.md`.
- Dev server on `:5173` matches the backend `BACKEND_CORS_ORIGINS` whitelist.

## Environment variables

Copy `.env.example` to `.env.local` and set:

| Variable | Meaning |
|---|---|
| `VITE_API_BASE_URL` | KNEXUS backend origin (no trailing slash). |
| `VITE_API_TIMEOUT_MS` | Optional Axios timeout override (default 30000). |
| `VITE_DATA_MODE` | `mock` (default in tests) uses local JSON fixtures under\n| `src/mocks/data/` served by `src/mocks/` with no network access; `live` queries\n| the configured backend. The active mode is always shown in the sidebar; there\n| is no silent mock fallback after a live failure. |
| `VITE_MOCK_DELAY_MS` | Optional artificial delay for mock responses (default 150; 0 disables). |

## Stack notes

- Tailwind CSS connects via `@tailwindcss/vite` and `src/styles/tokens.css` (shadcn semantic tokens).
- shadcn/ui primitives (radix-nova style) live in `src/components/ui`; class merging comes from the
  official `cn` package re-exported once through `src/lib/utils.ts`.
- Application shell: React Router (`src/app/router`), TanStack Query provider (`src/app/providers`),
  shared layout components (`src/components/layout`).
- API boundaries: `src/lib/api/index.ts` is the single API entry — `getDocumentApi()` /
  `getAssistantApi()` return either the live (axios + Zod contract validation) or the mock
  (canonical fixtures) implementation based on `VITE_DATA_MODE`. Feature components depend on the
  `DocumentApi` / `AssistantApi` interfaces only.
- Zod contracts (`src/lib/api/contracts.ts`) mirror `contracts/phase1/models.py` including its
  cross-field invariants; drift from the handwritten types fails the typecheck through
  mutual-assignability tests in `src/lib/api/__tests__/contracts.test.ts`.
- The browser must never hold provider API keys; all generation/embedding calls go
  through Hassan's backend routes.
