# Phase 2 Changelog — KNEXUS Frontend (Z02: typed client & explicit mock/live modes)

**Date:** 5 November 2026 · **Branch:** `dev-zaid` (uncommitted) · **Team-guide task:** Z02  
**Scope honored:** all changes inside `frontend/` (git-verified). No backend or teammate-owned files touched. Dashboard and shell preserved; no Z03/Z04 features implemented.

## Overview

Phase 2 established a single, typed API boundary for the KNEXUS frontend and added a local JSON mock data mode so the frontend can be developed and tested without a running backend. Features depend only on shared service interfaces (`DocumentApi`, `AssistantApi`); the concrete implementation (live axios client vs. local mock) is selected at startup by the `VITE_DATA_MODE` environment variable and is invisible to components. Runtime payload validation with Zod is applied identically to mock and live responses.

## Architecture

All implementation paths below are relative to the frontend source root `frontend/app/src/` unless noted otherwise.

**Single API boundary** (`lib/api/index.ts`): `getDocumentApi()` and `getAssistantApi()` are the only factory entry points. Each returns either the live or mock implementation based on `VITE_DATA_MODE`; features never import axios or fixtures directly and never change when modes are switched.

**Live implementation** (`lib/api/live/`): real KNEXUS routes through the shared Axios client (`lib/api/client.ts`), every response parsed through Zod contracts before use, contract failures throw `ContractViolationError` (payload never rendered), Axios errors rethrow for central normalization via `toApiError`. Assistant requests always pin `stream: false`.

**Mock implementation** (`mocks/`): local JSON fixtures under `mocks/data/`, an in-memory store (`mocks/store.ts`), feature-operation handlers (`mocks/handlers/documents.ts`, `mocks/handlers/assistant.ts`), and a central dispatcher (`mocks/mock-server.ts`) that re-parses every response through Zod before dispatch. Fixture files are never written; store mutations are in-memory only.

**Shared contracts** (`lib/api/contracts.ts`): a single Zod module mirroring `contracts/phase1/models.py` with cross-field invariants as refinements (abstention shape, `[N]` citation-marker matching, unique citation ids, status/progress consistency, page bounds). Handwritten feature types are pinned to Zod-inferred types by mutual-assignability tests, so contract drift fails `typecheck`.

**Mode selection** (`lib/api/mode.ts`): `VITE_DATA_MODE` (`live` default, `mock` opt-in) is read once at startup; unknown values fail closed. `VITE_MOCK_DELAY_MS` applies an artificial delay only in mock mode. The sidebar footer shows the active mode visibly. There is **no silent mock fallback** after a live error — live failures remain errors.

## JSON fixture inventory

Fixtures live in `frontend/app/src/mocks/data/`. All are contract-shaped; verbatim canonical fixtures are byte-for-byte copies of `contracts/phase1/examples/*.json`. `document-list.json` is synthetic frontend data (a realistic 6-document corpus) and is the only fixture not copied verbatim from the canonical examples.

| File | Source | Content |
|---|---|---|
| `frontend/app/src/mocks/data/document-list.json` | Synthetic (frontend) | Realistic 6-document corpus across all four statuses (3 complete, 1 queued, 1 processing, 1 failed); `meta { total: 6, limit: 20, offset: 0 }`. |
| `frontend/app/src/mocks/data/document-detail.json` | Verbatim canonical | Canonical `document-detail.json`. |
| `frontend/app/src/mocks/data/document-status-queued.json` | Verbatim canonical | Canonical `document-queued.json`. |
| `frontend/app/src/mocks/data/document-status-processing.json` | Verbatim canonical | Canonical `document-processing.json`. |
| `frontend/app/src/mocks/data/document-status-complete.json` | Verbatim canonical | Canonical `document-complete.json`. |
| `frontend/app/src/mocks/data/document-status-failed.json` | Verbatim canonical | Canonical `document-failed.json`. |
| `frontend/app/src/mocks/data/query-answer.json` | Verbatim canonical | Canonical `query-answer.json` (answer + 1 citation, not abstained). |
| `frontend/app/src/mocks/data/query-abstention.json` | Verbatim canonical | Canonical `query-abstention.json` (null answer, empty citations, reason). |
| `frontend/app/src/mocks/data/provider-error.json` | Verbatim canonical | Canonical `provider-error.json` (`PROVIDER_UNAVAILABLE`, served at 503). |
| `frontend/app/src/mocks/data/validation-error.json` | Verbatim canonical | Canonical `validation-error.json` (`VALIDATION_ERROR`, served at 422). |
| `frontend/app/src/mocks/data/upload-accepted.json` | Verbatim canonical | Canonical `upload-accepted.json` (accepted message shape). |
| `frontend/app/src/mocks/data/query-request.json` | Verbatim canonical | Canonical `query-request.json` (`stream: false` pinned). |
| `frontend/app/src/mocks/data/upload-metadata.json` | Verbatim canonical | Canonical `upload-metadata.json`. |

No API fields or response shapes were invented; runtime compositions use only contract-defined fields.

## Mock/live configuration

- Set `VITE_DATA_MODE=mock` to use local fixtures with no network (default `live`). One variable, read once at startup; switching requires an env change plus restart — zero component changes.
- `VITE_MOCK_DELAY_MS` (default 150 ms; `0` in tests) applies an artificial delay only in mock mode.
- The sidebar footer always shows the active mode ("Mock data mode" / "Live API mode").
- **No silent mock fallback:** in `live` mode, backend failures reach `ErrorState` unchanged; the mock layer is never consulted.
- Offline run: `VITE_DATA_MODE=mock npm run build && VITE_DATA_MODE=mock npm run preview` — no backend required.

## Simulated operations

| Operation | Mock behavior |
|---|---|
| GET documents | Paginated slice of the in-memory list seeded from `document-list.json`. |
| GET document details | Canonical fixture for the seeded document; contract-empty composite (`description: null`, `metadata: {}`) for documents without a canonical detail fixture. |
| GET document status | Seeded documents keep their fixture state. Uploaded documents progress **queued → processing → complete** over successive status polls (realistic chunk totals; `total == processed`, progress 100 at complete). |
| POST document upload — rejection before acceptance | Metadata validation fails (duplicate or empty `allowed_roles`) → canonical `VALIDATION_ERROR`; no entry is created. |
| POST document upload — acceptance | Entry appended to the in-memory store only (fixture files never written); fresh `crypto.randomUUID()` ids; canonical accepted message; status `queued`. |
| POST document upload — subsequent asynchronous processing failure | Filename containing `fail` → failed ingestion with canonical `INVALID_FILE` failure shape (`failure_code`, `failure_message`). |
| POST query | Canonical answer fixture by default; documented absence keywords → canonical abstention; "provider unavailable" → canonical `PROVIDER_UNAVAILABLE` envelope (503); "network failure" → `ERR_NETWORK` transport error. |

## Runtime validation

- Every fixture is parsed through its Zod schema at module import (`mocks/store.ts`); every mock-server response is re-parsed before dispatch — identical schema discipline as live responses.
- Handwritten feature types stay pinned to Zod-inferred types by mutual-assignability tests (contract drift fails `typecheck`).
- Error envelope canonical form `{ detail, code, request_id }` is preserved for live transport errors and mock-emulated errors alike via `toApiError` (`lib/api/error.ts`).

## Verification results

All checks executed against `frontend/app`, 5 November 2026:

| Check | Result |
|---|---|
| `npm run typecheck` (strict, including tests and type-assignment guards) | ✅ 0 errors |
| `npm run test` (Vitest, node environment) | ✅ 4 files, 40 tests passed |
| `npm run lint` (oxlint) | ✅ 0 findings |
| `npm run build` (production) | ✅ built ~303 ms (pre-existing >500 kB chunk warning deferred to Z05/Z06) |
| Mock mode E2E (headless Chrome, production build, no backend running) | ✅ "Mock data mode" badge; dashboard rendered the fixture corpus (3 complete / 1 queued / 1 processing / 1 failed); correct status chips; no error state |
| Live mode E2E (headless Chrome, backend offline) | ✅ "Live API mode" badge; honest `ErrorState` + retry; zero fabricated counts rendered; no mock data leak |
| Git scope | ✅ `git status` shows changes only under `frontend/` |

No additional validation or test execution is claimed beyond what is listed above.

## Complete file inventory (created, modified, deleted)

| File | Why |
|---|---|
| `frontend/app/src/mocks/store.ts` | Created — in-memory mock store seeded by deep-copying fixtures; lifecycle/progress simulation; trigger vocabulary and envelope helpers. |
| `frontend/app/src/mocks/handlers/documents.ts` | Created — mock handlers for GET list/detail/status and POST upload. |
| `frontend/app/src/mocks/handlers/assistant.ts` | Created — mock handler for POST query (answer, abstention, provider-error, network-error triggers). |
| `frontend/app/src/mocks/mock-server.ts` | Created — central dispatcher; re-parses every mock response through Zod before dispatch. |
| `frontend/app/src/mocks/data/document-list.json` | Created — synthetic 6-document corpus fixture (all four statuses). |
| `frontend/app/src/mocks/data/document-detail.json` | Created — verbatim canonical fixture. |
| `frontend/app/src/mocks/data/document-status-queued.json` | Created — verbatim canonical fixture. |
| `frontend/app/src/mocks/data/document-status-processing.json` | Created — verbatim canonical fixture. |
| `frontend/app/src/mocks/data/document-status-complete.json` | Created — verbatim canonical fixture. |
| `frontend/app/src/mocks/data/document-status-failed.json` | Created — verbatim canonical fixture. |
| `frontend/app/src/mocks/data/query-answer.json` | Created — verbatim canonical fixture. |
| `frontend/app/src/mocks/data/query-abstention.json` | Created — verbatim canonical fixture. |
| `frontend/app/src/mocks/data/provider-error.json` | Created — verbatim canonical fixture. |
| `frontend/app/src/mocks/data/validation-error.json` | Created — verbatim canonical fixture. |
| `frontend/app/src/mocks/data/upload-accepted.json` | Created — verbatim canonical fixture. |
| `frontend/app/src/mocks/data/query-request.json` | Created — verbatim canonical fixture. |
| `frontend/app/src/mocks/data/upload-metadata.json` | Created — verbatim canonical fixture. |
| `frontend/app/src/lib/api/mode.ts` | Modified — `VITE_API_MODE`→`VITE_DATA_MODE`; `resolveApiMode`/`ApiMode`→`resolveDataMode`/`DataMode`; fail-closed on invalid values. |
| `frontend/app/src/lib/api/index.ts` | Modified — factory imports mock implementations from `@/mocks/mock-server`; mode resolved via `getDataMode()`. |
| `frontend/app/src/components/layout/app-sidebar.tsx` | Modified — mode badge reads `getDataMode()`; no silent fallback wording. |
| `frontend/app/.env.example` | Modified — documents `VITE_DATA_MODE` and `VITE_MOCK_DELAY_MS`; removes `VITE_API_MODE`. |
| `frontend/app/README.md` | Modified — test script, env-var table, mode explanation, stack notes updated for `VITE_DATA_MODE`. |
| `frontend/app/vite.config.ts` | Modified — removed `server.fs.allow` (fixtures now inside `frontend/`); `import.meta.dirname`. |
| `frontend/app/vitest.config.ts` | Modified — defines `VITE_DATA_MODE=mock` and `VITE_MOCK_DELAY_MS=0`. |
| `frontend/app/tsconfig.node.json` | Modified — includes `vitest.config.ts`. |
| `frontend/app/package.json` | Modified — added `test` script; added `zod` and `vitest` dependencies. |
| `frontend/app/src/lib/api/contracts.ts` | Created (Phase 2 base) — single Zod contract module with cross-field refinements. |
| `frontend/app/src/lib/api/error.ts` | Modified (Phase 2 base) — `toApiError` normalizes canonical envelope, `ContractViolationError`, `MockApiError`, transport failures. |
| `frontend/app/src/lib/api/contract-violation.error.ts` | Created (Phase 2 base) — Zod failure is never rendered; carries endpoint + issue paths. |
| `frontend/app/src/lib/api/mock-api.error.ts` | Created (Phase 2 base) — deterministic mock-mode canonical-envelope errors. |
| `frontend/app/src/lib/api/live/transport.ts` | Created (Phase 2 base) — injectable `ApiTransport` + `axiosTransport`. |
| `frontend/app/src/lib/api/live/live-document.api.ts` | Created (Phase 2 base) — live `DocumentApi` with Zod parsing and multipart upload. |
| `frontend/app/src/lib/api/live/live-assistant.api.ts` | Created (Phase 2 base) — live `AssistantApi`; pins `stream: false`. |
| `frontend/app/src/features/documents/services/document.api.ts` | Created (Phase 2 base) — `DocumentApi` interface. |
| `frontend/app/src/features/assistant/services/assistant.api.ts` | Created (Phase 2 base) — `AssistantApi` interface. |
| `frontend/app/src/lib/api/mock/` | Deleted — superseded by `frontend/app/src/mocks/`; removed external `contracts/` import dependency. |
| `frontend/app/features/documents/services/document.service.ts` | Deleted — replaced by `DocumentApi` interface + live/mock implementations. |
| `frontend/app/features/assistant/services/assistant.service.ts` | Deleted — replaced by `AssistantApi` interface + live/mock implementations. |

## Remaining work

1. Z03 (document workflows): real upload/list/status UI consuming these same interfaces; bounded polling; double-submit prevention.
2. Z04 (assistant): chat UI consuming `AssistantApi`; abstention/citation rendering.
3. Z05: live integration against the real backend (mode stays `live`); report mismatches instead of editing contracts.
4. Mock-layer composites (upload store, status lifecycle) are mock-only, gated behind `VITE_DATA_MODE=mock`, and contain only contract-defined fields.
