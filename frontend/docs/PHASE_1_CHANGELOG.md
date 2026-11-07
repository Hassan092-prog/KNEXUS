# Phase 1 Changelog — KNEXUS Frontend

**Branch:** `dev-zaid` (uncommitted at time of writing, per review decision) · **Date:** 5 November 2026
**Scope honored:** every change is inside `frontend/`. `git status` confirmed zero modifications outside `frontend/app/` and `frontend/docs/`.

---

## A. Files created

### Documentation (`frontend/docs/`)

| File | Purpose |
|---|---|
| `frontend/docs/PHASE_1_RECONNAISSANCE.md` | Repository/frontend/backend/teammate inspection report with architecture recommendation (Steps A, C) |
| `frontend/docs/API_MAPPING.md` | Verified endpoint-by-endpoint API mapping with request/response shapes, error codes, and explicit uncertainties (Step B) |
| `frontend/docs/PHASE_1_CHANGELOG.md` | This report |

### Application (`frontend/app/`)

**Configuration & tooling**

| File | Purpose |
|---|---|
| `frontend/app/.env.example` | Env contract: `VITE_API_BASE_URL`, optional `VITE_API_TIMEOUT_MS`; documents the port-5173 CORS constraint |
| `frontend/app/components.json` | shadcn/ui config (style `radix-nova`, lucide icons, CSS variables) |
| `frontend/app/tsconfig.app.json` *(modified)* | Strict TS enabled, `@/*` path alias added, `baseUrl` removed (TS 7 removed the option) |
| `frontend/app/tsconfig.node.json` *(unchanged)* | — |
| `frontend/app/vite.config.ts` *(modified)* | Added `@` alias and Tailwind v4 plugin wiring |
| `frontend/app/.oxlintrc.json` *(modified)* | Ignored `src/components/ui/**` (shadcn generated code triggers a fast-refresh warnings-only rule) |
| `frontend/app/package.json` *(modified)* | Dependencies below |
| `frontend/app/index.html` *(modified)* | Title `KNEXUS` |
| `frontend/app/.gitignore` *(unchanged)* | — |

**Design system / tokens**

| File | Purpose |
|---|---|
| `frontend/app/src/styles/tokens.css` | Shadcn-generated design tokens relocated here (light/dark oklch semantic tokens, fonts, radii, sidebar/chart vars) — single token source of truth |
| `frontend/app/src/index.css` *(modified)* | Imports Tailwind, animations, Geist font, tokens; base layer styles |

**shadcn/ui primitives** (generated via CLI into `src/components/ui/`) — moved from the CLI's stray `@/` path into `src/`:

`button.tsx`, `badge.tsx`, `card.tsx`, `alert.tsx`, `breadcrumb.tsx`, `separator.tsx`, `skeleton.tsx`, `sheet.tsx`, `tooltip.tsx` (+ CLI-generated `src/lib/utils.ts` containing `cn()`).

**Application shell (`src/app/`)**

| File | Purpose |
|---|---|
| `src/app/router/index.tsx` | `createBrowserRouter` with `/`, `/assistant`, `/documents`, `/documents/:id`, `*` |
| `src/app/router/not-found-page.tsx` | 404 page |
| `src/app/providers/app-providers.tsx` | Central TanStack Query client (retry disabled, focused refetch off) |
| `src/app/layouts/root-layout.tsx` | Shell: skip link, sidebar, header, main scroll container |

**Layout components (`src/components/layout/`)**

| File | Purpose |
|---|---|
| `app-sidebar.tsx` | Brand, primary nav with active state + `aria-current`, `soon` badges for placeholder routes, mobile Sheet drawer, demo-mode footer note |
| `app-header.tsx` | Breadcrumbs per route, hamburger (mobile nav), real backend `API docs` link |
| `nav-config.ts` | Typed nav items (Lucide icons), breadcrumb resolver |

**Shared components (`src/components/shared/`)**

| File | Purpose |
|---|---|
| `page-header.tsx` | Consistent page title / description / action slot |
| `empty-state.tsx` | Configurable empty-state (icon, action) |
| `error-state.tsx` | Canonical error rendering: safe backend detail, error code, request id, retry |
| `status-badge.tsx` | Document-state chip (queued/processing/complete/failed visual mapping) |
| `loading-indicator.tsx` | Accessible spinner with `role="status"` |

**API foundation (`src/lib/`, `src/types/`)**

| File | Purpose |
|---|---|
| `src/lib/env.ts` | Single env resolver (base URL + timeout) with dev-mode fallback warnings |
| `src/lib/api/client.ts` | Shared Axios instance: baseURL from env + `/api/v1`, timeout, JSON content type; never sends identity fields |
| `src/lib/api/error.ts` | `toApiError` normalization of canonical `{detail, code, request_id}` envelope and transport failures |
| `src/types/env.d.ts` | Typed `ImportMetaEnv` augmentation |
| `src/types/api.ts` | Canonical error contracts (`ApiErrorCode`, `ApiErrorResponse`) |

**Feature modules (`src/features/`)**

| File | Purpose |
|---|---|
| `documents/types/document.types.ts` | TypeScript contracts mirrored from `contracts/phase1/models.py` (DocumentSummary/Detail/List/Status/UploadAccepted/PageMeta/UploadMetadata) |
| `documents/services/document.service.ts` | Verified-only bindings: list/detail/status + multipart upload method |
| `documents/components/document-library-page.tsx` | Placeholder page (no fabricated rows) |
| `documents/components/document-detail-page.tsx` | Placeholder page using the real `:documentId` param |
| `assistant/types/assistant.types.ts` | Query/QueryResponse/Citation/QueryMeta contracts |
| `assistant/services/assistant.service.ts` | `POST /query` binding (always `stream:false`) |
| `assistant/components/assistant-page.tsx` | Placeholder page (no fabricated chat) |
| `dashboard/hooks/use-dashboard-overview.ts` | Real-data overview hook: pages `GET /documents` (≤5 pages/500 docs cap, `capped` flag) accumulating backend-faithful status counts |
| `dashboard/components/dashboard-page.tsx` | Real-data overview: total + per-status counts + recent documents (real ids/titles/statuses/timestamps), loading skeletons, EmptyState, ErrorState with retry |

**Entry**

| File | Purpose |
|---|---|
| `src/main.tsx` *(modified)* | Mounts `AppProviders` + `RouterProvider` |

## B. Files modified

See tables above (tsconfig/vite/oxlint/package.json/index.html/index.css/main.tsx .env additions). Core behavior preserved; no backend file touched.

## C. Files deleted

| File | Why |
|---|---|
| `frontend/app/src/App.tsx` | Superseded by router pages (was a Z01 placeholder) |
| `frontend/app/public/icons.svg`, previously unneeded Vite branding assets | Cleaned up during Z01 — no other deletions |
| *(temp)* CLI-generated `frontend/app/@/` directory | shadcn CLI ignored the tsconfig alias; files were moved into `src/` and the stray folder removed |

## D. Architecture summary

- **Folder structure:** `app/` (router/providers/layouts) · `components/ui|shared|layout` · `features/{dashboard,documents,assistant}/{components,hooks,services,types}` · `lib/{api,utils,env}` · `types/` · `styles/`.
- **Component architecture:** shadcn primitives → shared composed components (PageHeader, EmptyState, ErrorState, StatusBadge, LoadingIndicator) → feature pages. No duplicated markup; presentation only, data via hooks.
- **Routing:** data router with `RootLayout`; route-specific pages under features; typed 404.
- **API client:** one Axios instance (`lib/api/client.ts`) from env-configured base URL; feature services are the only backend callers; `toApiError` normalizes errors once.
- **Type organization:** backend contracts mirrored 1:1 in feature `types/` + shared `types/api.ts`. Runtime payload validation intentionally deferred (mock-mode phase Z02 will tighten this).
- **Design system:** oklch semantic tokens in `styles/tokens.css`, Geist typography, consistent radius (`--radius` scale), buttons at fixed heights (via shadcn sizing), consistent spacing utilities.

## E. Backend/API findings

- All 6 Phase 1 endpoints verified implemented (`see API_MAPPING.md`); no contract shape changes needed.
- **Mismatches/limitations (documented, not fixed):**
  1. No retry/deletion/auth/history/streaming endpoints — placeholders avoid inventing them.
  2. No upload dedup — frontend must own double-submit prevention (future phase).
  3. `Health` endpoint still reports Ollama reachability; hosted adapters pending Hassan/Naveed — UI shows nothing derived from it this phase.
  4. CORS only whitelists 3000/5173; dev server pinned to 5173.
- This phase deliberately did **not** introduce a mock/live mode indicator or fixtures — that is Z02 scope per the team guide (API layer exposes only real bindings; no fixture fallback).

## F. Dependencies

Added at runtime: `react-router-dom@7.18.5`, `@tanstack/react-query@5.106.1`, `axios@1.21.0`, `lucide-react@1.69.0`, `class-variance-authority@0.7.1`, `cn@0.5.2` (official shadcn class-merging engine — compiled, zero transitive deps; re-exported once via `src/lib/utils.ts`), `tailwind-merge@3.7.0` *(installed with the stack, removed later in final review)*, `radix-ui@1.8.1` (unified package used by shadcn v4 style), `tw-animate-css@1.4.0`, `shadcn@4.23.0` (moved to devDependencies — CLI only), `@fontsource-variable/geist@5.3.0` (Nova preset font), `clsx@2.1.1` *(installed with the stack, removed later in final review)*.

Removed before release: `clsx`, `tailwind-merge` (superseded by the self-contained `cn` engine — confirmed zero direct usage), and the individually installed `@radix-ui/react-slot`, `react-dialog`, `react-tooltip`, `react-separator` (superseded by the unified `radix-ui` package the style actually imports).

## G. Validation (actually executed 5 Nov 2026)

| Check | Result |
|---|---|
| `npm run typecheck` (strict TS, TS 7) | ✅ pass (0 errors) |
| `npm run lint` (oxlint) | ✅ 0 warnings after scoping shadcn `ui/` |
| `npm run build` | ✅ built in ~300 ms · **warning:** main chunk >500 kB (noted in H) |
| Dev server | ✅ HTTP 200 on `/`, `/documents`, `/documents/{id}`, `/assistant`, fallback `*` |
| Git scope | ✅ `git status` shows zero changes outside `frontend/` |

### Post-review verification additions (final code review, 5 Nov 2026)

- **Route rendering verified in the real DOM** (headless Chrome against `vite preview` production build): all five routes render the intended pages with correct active-nav state; SPA-fallback-independent. Backend-offline `/` shows ErrorState + Retry and renders **zero** conservative document-count markup (data honesty under failure).
- Review-only fixes applied: unified `cn` imports in the nine shadcn files to `@/lib/utils`; removed redundant `clsx`/`tailwind-merge` runtime deps; simplified `ErrorState` (`error: unknown`, single import); removed unused `dashboardOverviewQueryKey` export; refreshed the app README's stale stack notes.
- Full findings analysis, dependency audit, and the bundle-splitting recommendation are in [`PHASE_1_FINAL_REVIEW.md`](PHASE_1_FINAL_REVIEW.md).

## H. Remaining work (deferred by design)

1. Z02 — typed client hardening + explicit mock/live mode + fixture-driven mock data + runtime payload validation.
2. Z03 — actual document list/upload/status workflows; upload no-double-submit; status polling stop conditions.
3. Z04 — assistant chat, citation rendering, abstention UI.
4. Z05/Z06 — live AIP integration, deeper a11y/browser verification, code splitting for the >500 kB chunk (vendor splitting with `manualChunks` or route-level lazy loading).
