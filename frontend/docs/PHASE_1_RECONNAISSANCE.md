# Phase 1 Reconnaissance — KNEXUS Frontend

**Date:** 4–5 November 2026 · **Branch inspected:** `dev-zaid` (+ `main`, `origin/dev-hassan`, `origin/dev-naveed`)

## 1. Existing repository architecture

| Path | Purpose | Relevant to frontend? |
|---|---|---|
| `backend/app/` | FastAPI application (`main.py`, `api/v1/endpoints/{documents,query,health}.py`, `api/errors.py`, `api/dependencies.py`) | Yes — API source of truth |
| `backend/app/schemas/` | Canonical Pydantic schemas (re-exports `contracts/phase1/models.py`) | Yes — wire shapes |
| `backend/app/services/` | Ingestion (parse/chunk/embed/storage/processor), retrieval, generation (fake/ollama/hosted adapters) | Indirectly — determines behavior/status classification |
| `contracts/phase1/` | `models.py` (cross-field invariants), generated `schema.json`, 17 synthetic wire fixtures + manifest | Yes — canonical reference for TS types & mock data |
| `backend/alembic/` | Migrations (six pg tables; pgvector) | No |
| `docker/`, `docker-compose.yml` | PostgreSQL 5435 bootstrap | No |
| `docs/` | `API_SPEC.md` (route behavior), `PHASE_1_CONTRACT.md`, `TRD.md`, `PROJECT_STATUS.md`, playbook | Yes — cross-checked against code |
| `frontend/` | `README.md` (instructions) + `app/` (Z01 scaffold, created 5 Nov) | Yes — target directory |

Recent backend history still relevant:

- `68e08fd` hosted chat-completions adapter (Groq); `d5d0d8b` hosted (Google) embedding foundation + quota/dispatch policy (in `main`).
- Hosted integration is targeted but **demo-visible behavior unchanged**; public routes and response shapes are identical to the canonical contract.
- `docs/API_SPEC.md` explicitly matches the implemented routes; no newer, unmerged contract changes exist (checked PRs #1–#18).

## 2. Existing frontend architecture (as of this phase)

The Z01 scaffold in `frontend/app/` (committed? no — left uncommitted per earlier decision, but verified):

- Build: **Vite 8.3.6**, React **19.3.1**, TypeScript **~7.0.2** (native TS 7), Tailwind CSS **4.3.4** via `@tailwindcss/vite`.
- Lint: Oxlint. Dev server on `:5173` (backend CORS-whitelisted). Build/typecheck verified passing.
- State: none (single placeholder `App.tsx`). No router, no API client, no docs folders yet.
- **Gap found:** `tsconfig.app.json` lacks `"strict": true`; Z01 build passes without strict mode. Must be enabled in this phase.
- No shadcn/ui, design tokens, or component library — everything here is greenfield beyond the scaffold.

## 3. Backend architecture relevant to the frontend

- Async FastAPI, prefix `/api/v1`, correlation header `X-Request-ID` on every response.
- **Identity:** server-owned fixed demo actor (`user=…0031`, `org=…0032`, role `orgadmin` → effective `[orgadmin, manager, employee]`). Requests containing identity-ish query params or headers (`x-user-id`, `org_id`, …) are rejected with 422. There is **no login/auth**.
- Errors: canonical `{detail, code, request_id}` with fixed code set; validation errors return the same envelope with generic detail (422). CORS is limited to localhost origins, methods GET/POST/OPTIONS.
- Ingestion runs as an in-process background task behind a 202 — not a durable queue; polling `/{id}/status` is the accepted frontend pattern (statuses include total/progress percent; terminal states `complete`/`failed`).
- Retrieval: SQL tenant + role + status filters before pgvector top-k. Query returns 200-with-abstention when evidence is insufficient; provider faults raise 502/503/504.

## 4. Work completed by teammates

- **Hassan (backend):** H01–H06 merged (inception/chunk/embed/retrieve/API + persistence). Latest: hosted-embedding foundation (Google embedder), quota controls, dispatch policy — **code in `main`, behavioral change is internal**; public contract unchanged. Owns backend tests.
- **Naveed:** hosted-generation harness and evaluation (PRs #12, #13); latest `e2658b6` hosted evaluation harness with labeled case groups.
- **Team docs:** Playbook tasks Z01–Z06 own the frontend to Zaid. Z02 explicit mock mode is a *contract requirement* of the team, not a personal choice.
- Nothing is duplicated or overwritten: no other branch contains frontend code.

## 5. Existing reusable components and libraries

- Only React 19 + Tailwind v4 + Oxlint exist. Nothing else installed yet.
- Adoption pending (Step F/D): `react-router-dom`, `@tanstack/react-query`, `axios`, `class-variance-authority`/`clsx`/`tailwind-merge` (shadcn/ui prerequisites), Radix primitives, `lucide-react`, `react-hook-form`, `zod`.
- shadcn/ui will be added inside `frontend/app` once the CLI is available (it returns source files, not runtime deps).

## 6. API inventory (see API_MAPPING.md for the full table)

Verified against backend code (`backend/app/api/v1/endpoints/*.py`) and the canonical contract checker (`contracts/phase1/check.py`, validated fixtures 17 pass / 24 negative):

| Endpoint | Status |
|---|---|
| `GET /` + `GET /api/v1/health` | Implemented (health is *passive diagnostics*, not a readiness gate; always 200) |
| `POST /api/v1/documents/upload` | Implemented (single PDF/DOCX ≤ 10 MiB, repeated `allowed_roles`) |
| `GET /api/v1/documents` | Implemented (paginate via `limit`,`offset`) |
| `GET /api/v1/documents/{id}` | Implemented (404 / 403 for out-of-role) |
| `GET /api/v1/documents/{id}/status` | Implemented (requires uploader or orgadmin; demo actor is orgadmin) |
| `POST /api/v1/query` | Implemented (`stream=false` only; returns canonical QueryResponse) |
| Login/admin/streaming | **Not implemented** — Phase 2 |

## 7. API implementation status

- All six public routes verified as **implemented and merged**. No stub/route mismatch found in code inspection.
- Provider status is *configuration-dependent*: query works against `fake`/Ollama today; hosted Groq/gprovider adapters exist in the tree but the configured acceptance gate is pending Hassan/Naveed. Frontend must therefore handle `PROVIDER_UNAVAILABLE`/timeout cleanly.
- Health endpoint does not signal readiness of generation; the frontend should not treat it as an auth/pre-visit gate.

## 8. API-contract mismatches

None in the wire contract itself. Documented caveats:

1. **Backend upload behavior beyond contract** (`documents.py:67–113`): re-submission of the same file is accepted (no dedup); duplicate uploads become duplicate documents. Frontend must guard double-submission client-side (Z03 concern, but noted here).
2. `GET /documents/{id}/status` is restricted to the uploader or `orgadmin` — with the fixed demo actor this always succeeds, but the frontend should still render 403 gracefully for the future.
3. The `UploadAccepted.message` differs between README (`Document received…`) and backend code (`Upload accepted for processing.`); contract field *shape* is fine, display text is owner-rendered by the frontend, not echoed.
4. CORS allowlist lacks localhost ports other than 3000/5173 — frontend must run the dev server on 5173 or wait for backend CORS update. Not a blocker.
5. `docs/PHASE_1_TEAM_GUIDE.md` says "stream=false" accepts — verified true; `stream=true` is a **422**. Confirmed no mismatch.

## 9. Missing or incomplete backend capabilities (frontend must not assume)

- **No authentication / user/org management / role switching.** The "user/profile area" is out of scope; the sidebar should not simulate one.
- **No document deletion/retry endpoints** (only query/list/detail/status). Delete and retry UX is impossible to wire.
- **No streaming/Chat history/session endpoints.** Each `POST /query` returns one-shot response; sidebar history is not backend-supported.
- **No dashboard analytics endpoint.** No counts/audit route beyond the documents list — any dashboard numbers must derive from real `GET /documents` pagination meta, not fabrication.
- **No binary file-content download** of chunk/page sources is promised; citation sources are rendered from `excerpt` only.
- Hosted generation/embedding adapters are not yet acceptance-verified — `POST /query` can legitimately 503/504.

## 10. Recommended frontend architecture

Feature-based modular layout under `frontend/app/src/`:

```
src/app/       router, providers, layout shell (sidebar/header)
src/components/ui/       shadcn/ui primitives (Button, Card, Badge, ...)
src/components/shared/   EmptyState, ErrorState, StatusBadge, PageHeader, Section, LoadingSpinner
src/components/layout/   AppSidebar, AppHeader, ContentArea
src/features/documents/  components/hooks/services/types (document service only — no workflow yet)
src/features/assistant/  components/hooks/services/types (assistant service only — placeholders)
src/features/dashboard/  components/hooks/types (placeholder)
src/lib/api/             axios instance, base-url resolution, env config, error normalization
src/lib/utils/           cn() etc.
src/hooks/               shared hooks (useMediaQuery later for mobile menu)
src/types/               cross-feature TS contracts mirrored from backend
src/styles/              design-token CSS layer for Tailwind/shadcn
```

- **API layer:** one Axios instance (timeout, `X-Request-ID` propagation optional, JSON + multipart), typed contract modules derived 1:1 from `contracts/phase1/models.py` + fixtures, a single error-mapping utility producing `{code, detail, requestId, status}`.
- **Data fetching:** TanStack Query with per-domain query keys (`['documents','list',...]`, `['documents','detail',id]`, `['documents','status',id]`, `['query', sessionId]`), no client-side MOCK/live state divergence in Phase 1 — the shared/MOCK requirement lands in Z02 next phase; Phase 1 only establishes the boundary.
- **State:** no global state library in this phase (only BrowserRouter, QueryClient, and Tailwind theme context if needed).

## 11. Proposed Phase 1 implementation plan (Steps C–G)

| Task | Output |
|---|---|
| C — Architecture | Restructure scaffold into the tree above; enable `"strict": true` in tsconfig |
| D — Design system | Install Radix/shadcn primitives + `lucide-react`; define CSS-variable tokens (brand slate, semantic states, radius, shadow scales) in `styles/tokens.css`; build shadcn `button/input/textarea/select/card/badge/dialog/dropdown-menu/tooltip/breadcrumb/skeleton/alert/sheet` + shared (EmptyState, ErrorState, StatusBadge, PageHeader, LoadingIndicator) |
| E — App shell | React Router with `/`, `/assistant`, `/documents`, `/documents/:id`, `*` 404; Sidebar (logo, nav with active state, collapsible Sheet on mobile), Header (breadcrumb + page title), main scroll container |
| F — API client & types | Axios instance via `VITE_API_BASE_URL`; `.env.example`; TS contracts generated by hand from `models.py`; `features/documents/services/document.service.ts` + `features/assistant/services/assistant.service.ts`; TanStack QueryProvider |
| G — Responsiveness | Responsive sidebar (Sheet), no horizontal overflow, keyboard-accessible interactive elements, focus-visible rings, placeholder pages marked clearly as such |

All work stays inside `frontend/`. Backend untouched.

---

## Verification performed during inspection

- Read every backend endpoint file: `documents.py`, `query.py`, `health.py`, `dependencies.py`, `errors.py`, `main.py`, `demo_identity.py`, `retrieval/service.py`.
- Read canonical `contracts/phase1/models.py` and validated fixtures (`upload-accepted.json`, `document-list.json`, `document-processing.json`, `query-answer.json`, `query-abstention.json`, `validation-error.json`).
- Checked git branches `main`, `origin/dev-hassan`, `origin/dev-naveed` for frontend/overlapping work (none).
- Searched `.env.example`, `backend/app/core/config.py` for CORS/credential exposure constraints.
- Z01 scaffold (`frontend/app`) verified: `typecheck`, `build`, `lint` passed, dev server HTTP 200 (previous session).
