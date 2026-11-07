# KNEXUS — UI Polish Changelog

## 1. Objective

Refine the KNEXUS frontend from an early enterprise SaaS implementation into a polished, consistent application across four pages: Overview, Documents, Document Details, and Assistant. Improve page composition, information hierarchy, spacing, typography, surfaces, and empty/loading/disconnected states — without adding functionality that belongs to future phases (Z03 document management, Z04 assistant query workflow).

## 2. Problems Identified

| Page | Problem |
|------|---------|
| Overview | Status captions used technical jargon ("Terminal", "Non-terminal", "Ingestion running"); total count repeated in section heading; labels at 11px; nested Card around table; skeletons wrapped in Cards |
| Documents | Nested-card composition: bordered container → DataTable (border+shadow) → EmptyState (dashed border + card bg); empty table header looked broken |
| Document Details | Repeated "Not loaded / Not available / Not connected" per-field placeholders; looked like a broken form; nested cards |
| Assistant | Generic stacked EmptyState + QueryInput; no dedicated workspace feel; composer had minimal disabled styling |
| Shared | `StatCard` labels at 11px uppercase; `EmptyState` always forced dashed border + card background; `DataTable` had `shadow-sm` and empty `<thead>` |

## 3. Design Improvements

- Replaced technical status captions with user-facing language (e.g., "Ready for knowledge queries", "Currently being processed", "Waiting to be processed", "Requires attention")
- Removed redundant total-count repetition in Overview section heading
- Established consistent page composition: Page Header → Primary Content surface → sections with clear headings
- Applied consistent spacing rhythm (4/8/12/16/20/24/32/40px)
- Used sentence-case labels at readable sizes (12px+); no 10px/11px labels for regularly-read information
- Reduced nested borders, shadows, and containers
- Made empty, disconnected, loading, and unavailable states look intentional
- Preserved the navy/slate token system in `tokens.css`; no new color system

## 4. Overview Changes

- **Metric hierarchy**: `StatCard` padding increased (p-4 → p-5); labels in sentence case at `text-xs`; numeric value is strongest visual element (`text-2xl font-semibold tabular-nums`); captions at `text-xs`
- **Captions**: Replaced technical jargon with user-facing descriptions per the mandated mapping
- **Redundancy removed**: Removed the section Card that repeated "X documents accessible"; the total is already prominent in the first metric card
- **Recent documents**: Section heading + description instead of a Card wrapper; table rows use `hover:bg-muted/50` with subtle transition; document titles link to details with focus indicators; roles appear as secondary text under titles
- **States**: Loading shows metric skeletons + recent-document skeletons (mutually exclusive with error/empty); error uses `ErrorState` with retry; empty uses `EmptyState` variant `surface` inside the library surface without an extra card
- **Data integrity**: All values remain API-derived from `useDashboardOverview`; `capped`/`scanned` explanation preserved; no invented statistics

## 5. Documents Changes

- **Layout**: Removed nested bordered container + DataTable shadow + EmptyState card. Now a single `rounded-lg border border-border bg-card p-5` section surface contains the section header and the `EmptyState` with `variant="surface"`
- **Empty state**: `EmptyState` rendered inside the library surface (no dashed border, no card background); looks like it belongs to the surface, not a separate card
- **Table presentation**: `DataTable` no longer wraps in a bordered card with `shadow-sm`; uses `overflow-x-auto` container with clean header row; no empty `<thead>` body rows rendered when disconnected
- **Responsive**: Table uses horizontal scroll on narrow viewports; empty state stays centered and balanced

## 6. Document Details Changes

- **Grouped unavailable data**: Instead of six per-field "Not loaded / Not available" placeholders, two sections group the information: "Document information" (source type, roles, chunk count, created date — will appear when connected) and "Processing information" (status and chunk details — available in Z03)
- **Document identity**: Document ID displayed prominently in a monospace block at top of the section surface
- **Honest messaging**: No fabricated metadata, status, or progress bars; no invented processing percentages
- **Layout**: Single section surface with two-column grid on desktop, stacked on mobile

## 7. Assistant Changes

- **Workspace**: Single-column conversation workspace; conversation area shows a deliberate disconnected state with `BotIcon`, heading "Your knowledge assistant", subtitle, and "not connected yet" note
- **Composer**: `QueryInput` placed in its own section surface below the conversation area; improved disabled styling (`disabled:text-muted-foreground/40`, `disabled:cursor-not-allowed`); input has `min-w-0` for proper flex shrinking; send button remains disabled
- **Empty state**: Clear heading, subtitle, and phase note — no giant empty card with tiny message, no right-side panel imbalance
- **Future-ready**: Structure supports adding conversation messages, citations, loading, and error states in Z04 without restructuring
- **Exactly one composer**: No duplicate QueryInput

## 8. Shared Component Changes

| Component | Change |
|-----------|--------|
| `StatCard` | Padding p-4 → p-5; labels sentence-case `text-xs` (was `text-[11px]` uppercase); caption `mt-2` spacing; consistent height via `flex h-full flex-col justify-between` |
| `EmptyState` | Added `variant` prop: `default` (full-page, dashed border, card bg), `surface` (compact, inside surfaces), `disconnected` (workflow-not-connected); icon sizes scaled per variant |
| `DataTable` | Removed `shadow-sm` and outer card wrapper; uses `overflow-x-auto` container; clean header row with `bg-muted/50`; no empty body rows |
| `PageHeader` | Unchanged (already follows conventions) |
| `StatusBadge` | Unchanged (already uses centralized semantic status tokens) |
| `DocumentTypeIcon` | Unchanged (restrained, compact) |

## 9. Responsive Improvements

- Overview metric grid: `grid-cols-1` mobile → `sm:grid-cols-3` tablet → `lg:grid-cols-5` desktop
- Overview recent-documents table: `overflow-x-auto` prevents horizontal overflow on mobile
- Document Details: two-column grid on `sm+`, stacked single column on mobile
- Assistant: stacked sections; conversation area centered on all widths
- No clipped page titles, no overlapping actions, no buttons outside viewport
- Focus indicators and keyboard navigation preserved throughout

## 10. Accessibility Improvements

- Heading hierarchy maintained (h1 via PageHeader, h2 for sections)
- Semantic HTML: `<section>`, `<table>` with `<thead>`, `<button>` for actions
- Focus indicators preserved via `focus-visible:ring-2 focus-visible:ring-ring`
- Status meaning does not depend on color alone (StatusBadge includes status text label)
- Document title links have visible focus rings
- Skip-to-content link preserved in root layout
- Disabled QueryInput communicates non-interactive state

## 11. Exact Files Modified

1. `src/features/dashboard/components/dashboard-page.tsx`
2. `src/features/documents/components/document-library-page.tsx`
3. `src/features/documents/components/document-detail-page.tsx`
4. `src/features/assistant/components/assistant-page.tsx`
5. `src/features/assistant/components/query-input.tsx`
6. `src/components/shared/stat-card.tsx`
7. `src/components/shared/empty-state.tsx`
8. `src/features/documents/components/data-table.tsx`
9. `frontend/docs/UI_POLISH_CHANGELOG.md` (this file)

## 12. Tests Executed

| Check | Command | Result |
|-------|---------|--------|
| TypeScript typecheck | `npm run typecheck` | 15 pre-existing errors (all in `src/lib/api/`, `src/mocks/`, and `use-dashboard-overview.ts` which calls the stubbed API); **0 new errors** |
| Lint | `npm run lint` | Passes cleanly |
| Unit tests | `npm run test` | No test files exist (pre-existing) |
| Production build | `npm run build` (vite build portion) | **Succeeds** — 2245 modules transformed, bundles emitted |

Note: The `tsc -b` portion of `npm run build` fails due to pre-existing type errors in `src/lib/api/index.ts` (stubbed API) and `src/mocks/` (missing modules) — files outside the approved scope that cannot be modified. Vite's production build itself succeeds.

## 13. Build Result

Vite production build: **successful**. All 2245 modules transform and bundle into `dist/`. The `tsc -b` typecheck step fails only on pre-existing errors in files outside the approved modification scope.

## 14. Scope Confirmation

- No backend files modified ✓
- No API contract changes ✓
- No `src/lib/api/` changes ✓
- No `src/mocks/` changes ✓
- No Z03 implementation ✓
- No Z04 implementation ✓
- No fake data, fake metrics, fake documents, fake responses, or fake citations ✓
- No new dependencies ✓
- All changes inside `frontend/app/src/` ✓

## 15. Remaining Issues

- Pre-existing `tsc -b` type errors in `src/lib/api/index.ts`, `src/mocks/handlers/`, `src/mocks/mock-server.ts`, `src/mocks/store.ts`, and `src/features/dashboard/hooks/use-dashboard-overview.ts` (lines calling the stubbed API). These exist on the baseline and are outside the approved scope.
- No unit/integration test files exist in the project (pre-existing).
- Browser screenshots could not be captured in this environment (no headless browser available); UI quality verified via code review, successful Vite build, and dev server runtime verification.
