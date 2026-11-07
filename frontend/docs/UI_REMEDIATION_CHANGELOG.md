# KNEXUS Frontend UI Remediation Changelog

## Summary

Visual and UX remediation of the KNEXUS frontend shell, design tokens, and page foundations. The result is a coherent, polished, enterprise-grade SaaS presentation layered on top of the existing technical architecture. Backend and API architecture are untouched.

All changes are confined to `frontend/app/src/` presentation files plus this documentation file. `src/lib/api/`, `src/mocks/`, the `DocumentApi`/`AssistantApi` interfaces, live/mock implementations, Zod contracts, React Query configuration, environment modes, and routes were not modified.

## Original problems identified

| # | Problem | Location |
|---|---------|----------|
| 1 | API Documentation nav item used an empty route (`to: ""`) and could resolve as active alongside the real page. | `nav-config.ts` |
| 2 | Dark theme sidebar primary token (`oklch(0.488 0.243 264.376)`) was a saturated blue, mismatching the main primary token and producing an excessively saturated active navigation appearance. | `tokens.css` |
| 3 | Inconsistent typography and spacing across pages; headings and secondary text varied in size/weight. | Multiple pages |
| 4 | Document library empty state implied a real API query had confirmed "no documents", when the list workflow is not yet connected. | `document-library-page.tsx` |
| 5 | Document detail page risked displaying fabricated metadata / progress values. | `document-detail-page.tsx` |
| 6 | Assistant page could imply a connected assistant with fabricated answers or citations. | `assistant-page.tsx` |
| 7 | `StatCard` lacked a defined surface, border, and consistent metric presentation. | `stat-card.tsx` |
| 8 | Sidebar active state used `sidebar-primary` (saturated in dark) rather than a restrained accent indicator. | `app-sidebar.tsx` |

## Design decisions

- **Color palette**: restrained navy/slate enterprise palette. Light: very light neutral background (`oklch(0.975 0.005 240)`), white cards, deep charcoal foreground (`oklch(0.16 0.01 242)`), muted borders. Dark: deep charcoal background (`oklch(0.16 0.01 240)`), slightly lighter card surface (`oklch(0.205 0.01 240)`), soft white foreground. Surfaces are distinguishable; no pure black.
- **Primary accent**: `oklch(0.22 0.012 242)` (light) / `oklch(0.922 0 0)` (dark). Accent is restrained blue used for interaction/selection only.
- **Sidebar primary alignment**: `--sidebar-primary` now equals `--primary` in both themes, eliminating the dark-theme saturated-blue mismatch. Active nav uses a narrow `border-sidebar-primary` accent plus a subtle `bg-sidebar-accent` fill.
- **Status colors**: muted, WCAG-AA-targeted semantic tokens (`--status-complete/processing/queued/failed-*` background/foreground) used consistently by `StatusBadge`. Never relies on color alone.
- **Radius hierarchy**: small controls 6px, inputs/buttons 8px, cards 10px, dialogs 12px (derived from `--radius = 0.625rem`).
- **Typography**: Geist throughout. Page heading `text-2xl` semibold tracking-tight; section headings `text-base` semibold; body `text-sm`; secondary/metadata `text-xs`/`[11px]`. Consistent weights, line heights, and margins across pages.
- **Elevation**: subtle `shadow-sm`/`shadow-md` only where meaningful; no shadow on every component; no borders around every individual element.
- **No fake data**: no fabricated charts, statistics, users, documents, answers, or citations. Unfinished workflows are explicitly labelled as not connected.

## Components modified

| File | Reason |
|------|--------|
| `src/components/layout/nav-config.ts` | API documentation converted to an external anchor (`external: true`, `href`); `external`/`href` fields added to `NavItem`; stable section keys; valid routes for all internal items. |
| `src/components/layout/app-sidebar.tsx` | Width set to 248px; active nav uses restrained accent (`border-sidebar-primary` + `bg-sidebar-accent`) instead of primary; consistent `size-4` icons; section headings; stable React keys; compact data-mode footer; mobile Sheet drawer. |
| `src/components/layout/app-header.tsx` | Minimal header: breadcrumbs + theme toggle only; duplicate "API docs" link removed (API docs lives in sidebar only); subtle bottom border; accessible menu/theme labels; mobile menu button. |
| `src/app/layouts/root-layout.tsx` | Shell: fixed sidebar (`lg:pl-[248px]`), sticky header, main scroll container; skip-to-content link. |
| `src/styles/tokens.css` | Refined light/dark semantic tokens; dark sidebar-primary aligned with primary; muted status colors; distinct dark surfaces; spacing/radius tokens. |
| `src/components/shared/stat-card.tsx` | Surface (`bg-card`), subtle border, consistent padding, prominent tabular value, label, optional icon/caption; equal card heights. |
| `src/components/shared/page-header.tsx` | Standardized h1 title + muted description + optional right actions; consistent hierarchy. |
| `src/components/shared/page-container.tsx` | Consistent max-width (`max-w-7xl`), padding (`px-4 py-6`, `lg:px-8`), responsive. |
| `src/components/shared/status-badge.tsx` | Consistent padding/height/font-size; muted status colors; terminal states visually distinct; dot indicator for processing. |
| `src/components/shared/document-type-icon.tsx` | Consistent PDF/DOCX icons, restrained color. |
| `src/components/shared/theme-provider.tsx` | Safe localStorage handling (try/catch), `.dark` class on `<html>`, no theme flash beyond the existing inline startup script. |
| `src/features/dashboard/components/dashboard-page.tsx` | Real API-derived metrics (total + five status counts), recent-documents table, mutually exclusive loading/error/empty/populated states, capped-data explanation. |
| `src/features/documents/components/document-library-page.tsx` | "Document library not connected" neutral empty state; no fabricated rows; not claiming the library is empty. |
| `src/features/documents/components/document-detail-page.tsx` | Neutral "Not loaded"/"Not available"/"Not connected" labels; no fabricated metadata, progress, or chunk values; no progress bar. |
| `src/features/documents/components/document-row.tsx` | Consistent column count/order/alignment with `DataTable` headers; truncated titles; hover feedback. |
| `src/features/documents/components/data-table.tsx` | Header/row column counts match; loading/empty/error separation; `overflow-x-auto` wrapper. |
| `src/features/assistant/components/assistant-page.tsx` | Exactly one `QueryInput`; no duplicate composer; no fabricated answers/citations; empty-state + explanation that workflow is not connected. |
| `src/features/assistant/components/query-input.tsx` | Single composer; disabled state explained; consistent input style. |

## Components created or removed

- Created: none (reused existing `PageHeader`, `StatCard`, `StatusBadge`, `EmptyState`, `ErrorState`, `DocumentTypeIcon`, `DataTable`, `DocumentRow`).
- Removed: none. (The duplicate Assistant composer that previously existed was already removed; exactly one `QueryInput` remains.)

## Navigation corrections

- API Documentation: `to: ""` retained only as an unused field on an `external: true` item; rendered as a standard `<a href="{apiBaseUrl}/docs" target="_blank" rel="noreferrer">`, never as a React Router destination. Only internal items use `to` with valid routes (`/`, `/documents`, `/assistant`).
- `Overview` uses `end: true` (exact match); `Documents`/`Assistant` use `end: false` so parent routes stay active while viewing children. Exactly one nav item is active per route.
- No duplicate API Documentation links: removed from header, kept in sidebar only.
- Stable React keys added for nav sections (`key={section.key}`) and items (`key={item.label}`).

## Theme changes

- Light: background `oklch(0.975 0.005 240)`, card `oklch(1 0 0)`, foreground `oklch(0.16 0.01 242)`.
- Dark: background `oklch(0.16 0.01 240)`, card `oklch(0.205 0.01 240)`, sidebar `oklch(0.14 0.01 240)` — distinguishable surface levels, no pure black.
- `--sidebar-primary` equals `--primary` in both themes; active nav uses `sidebar-accent` (restrained blue), fixing the prior saturated-blue dark sidebar.
- `ThemeProvider`: localStorage wrapped in try/catch (unavailable/blocked storage falls back to light), `.dark` toggled on `<html>`.
- `index.html` retains an inline startup script that applies a stored dark theme before hydration to avoid theme flash.

## Responsive improvements

- Desktop (1440px): fixed 248px sidebar, sticky header, page container `max-w-7xl`, 5-column metrics grid on dashboard (`lg:grid-cols-5`).
- Tablet (768px): metrics grid collapses (`sm:grid-cols-2`), tables wrapped in `overflow-x-auto`, sidebar hidden and replaced by Sheet drawer below `lg`.
- Mobile (375px): sidebar is a left Sheet; header menu button opens it; metrics stack single-column; table text stays readable (no shrinking to unreadable); touch targets use standard button sizes.
- Breakpoints used: `sm`, `lg`; `overflow-x-auto` on tables; `hidden lg:block` / `lg:hidden` for sidebar/Sheet.

## Accessibility improvements

- Skip-to-content link (focus-visible, fixed top-left).
- Semantic `<nav aria-label="Primary">`, `<header>`, `<main id="main-content">`.
- Menu button `aria-label="Open navigation menu"`; theme toggle `aria-label` toggles between light/dark.
- Focus rings (`focus-visible:ring-2 focus-visible:ring-ring`) preserved; no focus outlines removed without replacement.
- Buttons/links are semantic; no clickable `div`s for navigation.
- Status badges include a dot indicator (processing pulses) so status is not color-only.
- Truncated titles expose full text via `title` attribute / hover.
- Breadcrumb separators and current-page marking via `BreadcrumbPage`.

## Exact files changed

Presentation files (under `frontend/app/src/`):
- `src/components/layout/nav-config.ts`
- `src/components/layout/app-sidebar.tsx`
- `src/components/layout/app-header.tsx`
- `src/app/layouts/root-layout.tsx`
- `src/styles/tokens.css`
- `src/components/shared/stat-card.tsx`
- `src/components/shared/page-header.tsx`
- `src/components/shared/page-container.tsx`
- `src/components/shared/status-badge.tsx`
- `src/components/shared/document-type-icon.tsx`
- `src/components/shared/theme-provider.tsx`
- `src/features/dashboard/components/dashboard-page.tsx`
- `src/features/documents/components/document-library-page.tsx`
- `src/features/documents/components/document-detail-page.tsx`
- `src/features/documents/components/document-row.tsx`
- `src/features/documents/components/data-table.tsx`
- `src/features/assistant/components/assistant-page.tsx`
- `src/features/assistant/components/query-input.tsx`

Documentation:
- `frontend/docs/UI_REMEDIATION_CHANGELOG.md` (this file)

## Tests executed and results

Executed from `frontend/app/`:

| Check | Command | Result |
|-------|---------|--------|
| Lint | `npm run lint` (oxlint) | ✅ Passed — 0 findings |
| Typecheck | `npm run typecheck` (`tsc -b`) | ❌ Blocked by pre-existing `src/lib/` stubs |
| Unit tests | `npm run test` (vitest) | ❌ No test files exist (`src/**/*.test.*`) |
| Production build | `npm run build` (`tsc -b && vite build`) | ❌ Blocked by pre-existing `src/lib/` stubs |

### Pre-existing environment limitation (not introduced by this task)

`src/lib/` is gitignored and ships on disk as stubs (`getDocumentApi`/`getAssistantApi` throw "API not available in this checkout"); `src/lib/api/contracts.ts`, the live implementations, `mockDelay`, and `MockApiError` are absent. Consequently:

- Typecheck errors occur only in `src/mocks/handlers/*`, `src/mocks/mock-server.ts`, `src/mocks/store.ts` (import missing `@/lib/api/contracts`, `MockApiError`, `mockDelay`) and `src/features/dashboard/hooks/use-dashboard-overview.ts` (calls the stubbed `listDocuments` with arguments).
- None of the UI/presentation files I modified produce typecheck errors.
- Build cannot complete because `tsc -b` is a build prerequisite.
- No unit test files exist in the repository, so vitest reports "No test files found".

These conditions pre-date this remediation and are documented as out of scope: I am forbidden from modifying `src/lib/api/`, `src/mocks/`, live/mock implementations, Zod contracts, or React Query configuration. They would be resolved by restoring the complete (previously verified) `src/lib/` implementation, which is outside this task's frontend-presentation scope.

## Build result

Not produced in this checkout, blocked by the pre-existing `src/lib/` stubs at the `tsc -b` step (see above). Lint passes clean.

## Remaining issues

- `src/lib/` stubs block typecheck/test/build; restoring the full `src/lib/api/` (live + mock implementations, contracts, `mockDelay`, `MockApiError`) is required to run those commands end-to-end but is explicitly out of scope and forbidden.
- No unit test files exist in the repository; adding tests is out of scope.
- Z03 (document upload/list/detail workflows) and Z04 (assistant chat/streaming/citations) are intentionally deferred to later phases; the Documents, Detail, and Assistant pages are visual foundations explicitly labelled as not connected.
- Runtime visual verification (browser rendering at 1440/1280/768/375px in both themes) was performed via code review of Tailwind responsive classes rather than a live browser, because the dev server/build cannot run without the `src/lib/` implementation. Responsive behavior is encoded with `sm:`/`lg:` breakpoints, `overflow-x-auto` tables, and the mobile Sheet drawer.

## Scope confirmation

- Frontend-only presentation/interaction changes; no files outside `frontend/` touched.
- No backend modifications.
- No API contract changes; no Zod schema changes.
- No mock/live architecture changes; `VITE_DATA_MODE`, `VITE_API_BASE_URL`, `VITE_MOCK_DELAY_MS` preserved.
- Existing routes, `DocumentApi`/`AssistantApi` interfaces, and React Query configuration preserved.
