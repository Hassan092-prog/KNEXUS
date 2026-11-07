# KNEXUS Frontend — Phase 1 Implementation Audit

**Date:** 7 November 2026 · **Branch:** `dev-zaid` · **Working tree:** clean at audit start
**Scope:** complete the Phase 1 workflows inside `frontend/` without backend changes.

---

## 1. Existing implementation

### Application shell (working)

- Vite 8 + React 19 + TypeScript (strict), Tailwind v4, shadcn/ui ("radix-nova"),
  React Router v7 (`createBrowserRouter`), TanStack Query v5, Axios, Zod, Vitest, Oxlint.
- Shell: fixed sidebar (lg+) + Sheet drawer below lg, sticky breadcrumb header, theme
  toggle with dark mode, skip-to-content link. `RootLayout` → `PageContainer` → routes.
- Design tokens centralized in `src/styles/tokens.css` (Geist, oklch palette,
  status-color semantic tokens for queued/processing/complete/failed).
- Shared components: `PageHeader`, `PageContainer`, `StatCard`, `StatusBadge`,
  `EmptyState` (default/surface/disconnected), `ErrorState` (uses `toApiError`),
  `LoadingIndicator`, `DocumentTypeIcon`, `ThemeProvider`.
- UI primitives: alert, badge, breadcrumb, button, card, separator, sheet,
  skeleton, tooltip (shadcn).

### Feature layer

| Area | State at audit |
|---|---|
| Dashboard (`/`) | Implemented against `GET /documents`: paged overview scan (cap 5 × 100), status counters, recent-documents table, loading/error/empty states. |
| Document library (`/documents`) | **Visual foundation only** — deliberate "not connected" empty state, no data, no search/filter/pagination/upload. |
| Document detail (`/documents/:id`) | **Visual foundation only** — renders the route param, no fetches. |
| Assistant (`/assistant`) | **Visual foundation only** — one disabled composer, no submit, no answer/citation/abstention rendering. |
| Query keys | Not centralized (dashboard hook inlines `["documents","overview"]`). |

### API layer (partially broken)

- `features/documents/services/document.api.ts` and `features/assistant/services/assistant.api.ts`
  define correct typed interfaces (no invented fields).
- `lib/api/index.ts` is a **placeholder**: every method throws
  `"Document API not available in this checkout"` / `"Assistant API not available in this checkout"`.
- `lib/api/contracts.ts` is **referenced but missing** — the mocks layer imports
  contract schemas that were never committed.
- `lib/api/error.ts` is a stub: `toApiError` does no envelope handling; the
  `MockApiError` class and `mockDelay()` helper that the mocks rely on do not exist.
- Result: the checkout **does not typecheck** (`tsc -b` fails with 14 errors, all
  traceable to the three missing/stub API-layer modules).

### Mock layer (well designed, dormant)

- `mocks/data/*.json` mirrors `contracts/phase1/examples/*` fixtures (all verified
  identical except `document-list.json`, which extends the canonical 2-document
  example to 6 documents covering every status — still contract-valid; kept).
- `mocks/store.ts` seeds an in-memory store from fixtures parsed through the
  (missing) contract schemas; upload lifecycle simulation queued → processing →
  complete on successive polls; `fail` filename marker simulates failed ingestion;
  documented keyword triggers for abstention / provider error / network failure.
- `mocks/mock-server.ts` re-parses every handler output through the same Zod
  schemas used for live responses.

### Tests

- None exist. `vitest.config.ts` runs service-level tests in `node` env but no
  test files were committed.

## 2. Repository state

- Branch `dev-zaid`, clean tree, up to date with `origin/dev-zaid`; latest merge
  commit `aeb03e3`. Nothing to preserve beyond committed history. `dist/` exists
  locally but is ignored.

## 3. Backend reality (verified from source)

| Operation | Endpoint | Verified behavior |
|---|---|---|
| Health | `GET /api/v1/health` | Always-200 passives diagnostics; not a readiness gate. Not used by UI. |
| Upload | `POST /api/v1/documents/upload` | multipart `file` (1), repeated `allowed_roles`, optional `title`/`description`; ≤ 10 MiB; 202 `UploadAccepted` after DB commit; identity-ish form/query fields rejected 422; no dedup. |
| List | `GET /api/v1/documents` | `limit` 1–100 (default 20), `offset` ≥ 0; role-filtered; `created_at desc, id asc` ordering. |
| Detail | `GET /api/v1/documents/{id}` | 404 unknown/cross-tenant/deleted; 403 role denial. |
| Status | `GET /api/v1/documents/{id}/status` | latest ingestion attempt; queued totals/progress may be null; complete ⇒ progress 100; failed ⇒ safe code+message; 403 unless uploader or orgadmin (demo actor passes). |
| Query | `POST /api/v1/query` | `{question ≤4000, top_k 1–20 def 5, stream:false}`; 200 answer with citation `[N]` markers matching citation ids, or 200-with-abstention; 502/503/504 provider faults. |

- Errors are always `{ detail, code, request_id }` + `X-Request-ID` header; codes
  limited to the canonical enum. Error handlers cover FastAPI defaults too.
- No auth, no delete/download/retry, no streaming/conversation history, no server
  search/filter, no aggregate analytics. Demo actor is server-owned.
- CORS: localhost:3000/5173 (and 127.0.0.1). Dev server must stay on 5173.

## 4. Architecture problems

1. Missing `lib/api/contracts.ts` breaks every import of the contract layer.
2. Placeholder live API methods; no Axios client, no error normalization.
3. `mode.ts` lacks the `mockDelay` helper its consumers import.
4. Types duplicated by hand in `types/document.types.ts` / `assistant.types.ts`
   while contracts should be the single source (inference from Zod).
5. No centralized query keys; feature hooks invent their own.
6. Upload has not been implemented at all — multipart field semantics
   (repeated `allowed_roles`) must be exactly right against the backend form.
7. Browsing/pagination/search/filtering of the library does not exist.
8. No client-side collection filter story (backend exposes no search endpoint).

## 5. API mapping (frontend operation → backend call)

| Frontend operation | Backend call | Live service |
|---|---|---|
| Document list / collection scan | `GET /api/v1/documents?limit&offset` | `documentLiveApi.listDocuments` |
| Document detail | `GET /api/v1/documents/{id}` | `documentLiveApi.getDocument` |
| Processing status | `GET /api/v1/documents/{id}/status` | `documentLiveApi.getDocumentStatus` |
| Upload | `POST /api/v1/documents/upload` (FormData) | `documentLiveApi.uploadDocument` |
| Assistant query | `POST /api/v1/query` (JSON, `stream:false`) | `assistantLiveApi.submitQuery` |

## 6. Identified integration risks

- **Multipart shape:** `allowed_roles` must be repeated FormData fields; Axios
  default JSON content-type must not leak into the multipart request.
- **Computed vs real data:** no server aggregates — status counters must derive
  from list pages and be labelled "scanned" when capped.
- **Abstention is HTTP 200**; must never be rendered as an error.
- **Polling hygiene:** stop polling on terminal states; refresh detail/detail-list
  after transition; no fabricated progress for queued (totals unknown).
- **Identity leakage:** never send `org_id`/`user_id`/role fields; backend 422s.
- **Mock fixture mutations** must stay in the in-memory store; JSON never written.

## 7. Planned implementation sequence

1. **M1/M2 API foundation:** contract schemas (`lib/api/contracts.ts`), Axios
   client + error normalization (`client.ts`, `error.ts`), mode + delay helpers,
   live implementations, typed factory (`lib/api/index.ts`), inferred types.
2. **M3:** shared document collection scan (TanStack Query, cap-aware), document
   library (search/filter/pagination/actions), dashboard reuse of the same scan
   query + quick actions.
3. **M4:** upload dialog (dropzone, validation, roles, progress, invalidate +
   navigate), document detail page with controlled status polling and failure
   rendering, copy-id action.
4. **M5:** assistant page: composer, message bubbles, styled `[N]` markers,
   citation cards, abstention card, meta row, error/abstention separation.
5. **M6:** missing shadcn primitives (dialog, input, textarea, select, dropdown,
   table, progress, tabs, label, checkbox), mode banner, responsive/a11y pass.
6. **M7:** Vitest suites (API/error/contracts/factory + jsdom component tests),
   `npm run typecheck/test/lint/build`, written reports.
