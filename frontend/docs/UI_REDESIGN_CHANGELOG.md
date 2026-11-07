# UI Redesign Changelog — KNEXUS Frontend

**Date:** 5 November 2026 · **Branch:** `dev-zaid` (uncommitted) · **Task:** UI/UX Redesign  
**Scope honored:** all changes inside `frontend/`. No backend or teammate-owned files touched. No Z03/Z04 functionality implemented. Phase 1 and Phase 2 behavior fully preserved.

---

## Overview

Redesigned the KNEXUS frontend into a cohesive, polished enterprise knowledge-management application. The redesign establishes a unified global design system, fixes inconsistent navigation active states, removes fabricated/example content from the UI, and ensures all pages follow one consistent layout system. All existing API contracts, service interfaces, mock implementations, and backend code remain unchanged.

## Design Decisions

### Global Design System

Centralized in `src/styles/tokens.css` — the single token source of truth consumed by Tailwind v4 through `@theme inline`. Changing any token updates the entire application consistently.

**Brand identity (restrained navy/slate, not electric blue):**

| Token | Light | Dark | Use |
|---|---|---|---|
| Primary | `oklch(0.22 0.012 242)` deep navy/slate | `oklch(0.922 0 0)` | Brand, active nav, primary buttons |
| Primary foreground | `oklch(0.985 0 0)` | `oklch(0.22 0.012 242)` | Text on primary |
| Accent | `oklch(0.935 0.1 232)` restrained blue | `oklch(0.269 0 0)` | Links, subtle highlights |
| Accent foreground | `oklch(0.22 0.012 242)` | `oklch(0.985 0 0)` | Text on accent |
| Background | `oklch(1 0 0)` | `oklch(0.145 0 0)` | Page surface |
| Card | `oklch(1 0 0)` | `oklch(0.205 0 0)` | Elevated containers |
| Sidebar | `oklch(0.985 0 0)` | `oklch(0.145 0 0)` | Navigation column |
| Border | `oklch(0.9 0 0)` | `oklch(1 0 0 / 10%)` | Subtle separators |
| Shadow sm/md | Defined | Defined | Elevated surface shadows |

**Status colors (centralized, WCAG AA contrast, separate light/dark):**

| Status | Light bg | Light fg | Dark bg | Dark fg |
|---|---|---|---|---|
| complete | `oklch(0.22 0.012 242)` | `oklch(0.985 0 0)` | `oklch(0.922 0 0)` | `oklch(0.22 0.012 242)` |
| processing | `oklch(0.935 0.1 232)` | `oklch(0.145 0 0)` | `oklch(0.269 0 0)` | `oklch(0.985 0 0)` |
| queued | `oklch(0.965 0 0)` | `oklch(0.545 0 0)` | `oklch(0.269 0 0)` | `oklch(0.708 0 0)` |
| failed | `oklch(0.577 0.245 27.325 / 0.12)` | `oklch(0.577 0.245 27.325)` | `oklch(0.577 0.245 27.325 / 0.2)` | `oklch(0.704 0.191 22.216)` |

**Typography:** Geist (already loaded), heading scale `text-xl` → `text-base` → `text-sm` → `text-xs` → `text-[10px]`, tabular figures for counts.

**Theme:** Light theme is default. Dark theme supported via `.dark` class on `<html>`, persisted in localStorage, single theme toggle in header. Theme system uses React context (`theme-context.ts`, `theme-provider.tsx`, `use-theme.ts`).

### What Was Removed

- "Soon" badges on Documents and Assistant (they are accessible routes)
- Duplicate theme toggle from sidebar (now only in header)
- Fabricated metadata in DocumentDetailPage (no hardcoded "PDF", "employee", progress bar values)
- Fabricated example citation data in AssistantPage (no `exampleCitation` object)
- Duplicate query input in AssistantPage (single composer at bottom)
- Redundant citation-reference placeholder panel in AssistantPage
- Simultaneous skeleton + empty state rendering (states are now mutually exclusive)

## Component Inventory

### Design-system layer (`src/components/shared/`)

| File | Status | Purpose |
|---|---|---|
| `theme-context.ts` | Created | React context type definition for theme state |
| `theme-provider.tsx` | Created | Theme provider: localStorage persistence, `.dark` class on `<html>`, toggle |
| `use-theme.ts` | Created | `useTheme()` hook for consuming theme context |
| `theme-toggle.tsx` | Created | Light/dark switch button with Sun/Moon icons, accessible labels |
| `page-container.tsx` | Unchanged (prev phase) | Consistent page wrapper: `max-w-7xl`, standard padding |
| `page-header.tsx` | Modified | Consistent hierarchy, h1 title, small description, actions right |
| `stat-card.tsx` | Modified | Compact stat: prominent value + label + caption |
| `status-badge.tsx` | Unchanged | Centralized status tokens from `--status-*` CSS vars |
| `empty-state.tsx` | Modified | Consistent icon sizing and padding |
| `error-state.tsx` | Unchanged | Already canonical error rendering |
| `loading-indicator.tsx` | Unchanged | Already accessible spinner |
| `document-type-icon.tsx` | Unchanged (prev phase) | PDF/DOCX icon mapping from Lucide |

### Layout layer (`src/components/layout/`)

| File | Status | Purpose |
|---|---|---|
| `nav-config.ts` | Modified | Fixed active-state `end` props, removed placeholder concept |
| `app-sidebar.tsx` | Modified | Removed soon badges + theme toggle, compact mode indicator |
| `app-header.tsx` | Modified | Added theme toggle, compact breadcrumbs |
| `root-layout.tsx` | Modified | Uses `PageContainer` for consistent page layout |

### Feature layer

**Dashboard** (`src/features/dashboard/`):

| File | Status | Purpose |
|---|---|---|
| `components/dashboard-page.tsx` | Modified | 5 metrics (Total from `meta.total`, Complete/Processing/Queued/Failed from actual data), mutually exclusive loading/error/populated states, recent documents as table-like rows |
| `hooks/use-dashboard-overview.ts` | Unchanged | Data source already correct |

**Documents** (`src/features/documents/components/`):

| File | Status | Purpose |
|---|---|---|
| `document-library-page.tsx` | Modified | Table header foundation + empty state, no simultaneous skeleton/empty |
| `document-detail-page.tsx` | Modified | Removed all fabricated data, uses `Created` not `Updated` |
| `components/document-row.tsx` | Unchanged (prev phase) | Table row: type icon, title link, status chip, roles, Created |
| `components/data-table.tsx` | Modified | Header row only, no skeleton body (no data fetching yet) |

**Assistant** (`src/features/assistant/components/`):

| File | Status | Purpose |
|---|---|---|
| `assistant-page.tsx` | Modified | Single focused workspace, one query composer, no fabricated data |
| `components/message-bubble.tsx` | Unchanged | Presentation-only message container |
| `components/citation-card.tsx` | Unchanged | Presentation-only citation reference |
| `components/query-input.tsx` | Unchanged | Disabled-styled composer, not connected to API |

### Not modified (boundary confirmation)

| File | Reason |
|---|---|
| `src/lib/api/contracts.ts` | Zod schemas — boundary constraint |
| `src/lib/api/index.ts` | API boundary factory — boundary constraint |
| `src/lib/api/live/*` | Live implementations — boundary constraint |
| `src/lib/api/mock-api.error.ts`, `contract-violation.error.ts` | Error types — boundary constraint |
| `src/lib/api/mode.ts`, `error.ts`, `client.ts` | Mode/env/client — boundary constraint |
| `src/mocks/*` | All mock layer — boundary constraint |
| `src/features/documents/services/document.api.ts` | Interface — boundary constraint |
| `src/features/assistant/services/assistant.api.ts` | Interface — boundary constraint |
| `src/types/api.ts`, `src/types/env.d.ts` | Types — boundary constraint |
| Backend code | Out of scope |

## Page Redesign Summary

### Overview (`/`)
- Five metrics: **Total** (from `meta.total`), Complete, Processing, Queued, Failed — all derived from actual document data
- `capped` flag honored — status counts never imply complete corpus coverage when only partial data retrieved
- Recent documents: proper table-like rows with type icon, title link, status chip, roles, Created timestamp
- Loading, error, and populated states are **mutually exclusive** — never combined
- Empty state shown when `total === 0`

### Document library (`/documents`)
- Primary content surface = data table with column headers (Type, Title, Roles, Status, Chunks, Created)
- Empty state when no documents — no simultaneous skeleton rows
- No upload/search/filter/interactive pagination interactions (Z03 scope)

### Document detail (`/documents/:id`)
- Visual foundation only — metadata label/value structure, status card placeholder
- **No fabricated data** — no hardcoded source type, roles, chunk count, or progress values
- Uses `Created`, not `Updated` (no `updated_at` in contract)
- No data fetching or status polling (Z03 scope)

### Assistant (`/assistant`)
- Single focused conversation workspace
- One query composer at bottom — **no duplicate inputs**
- **No fabricated conversations or sample responses** — no `exampleCitation` data
- No redundant citation-reference panel
- Empty state with purposeful description
- No POST /query wiring, no streaming, no conversation history (Z04 scope)

### 404 (`*`)
- EmptyState with "Page not found" and "Return to overview" action

## Mock/Live Configuration

- `VITE_DATA_MODE` — `mock` (opt-in) or `live` (default), read once at startup
- `VITE_API_BASE_URL` — backend origin
- `VITE_MOCK_DELAY_MS` — artificial delay for mock mode only
- Sidebar footer shows active mode ("Mock data mode" / "Live API mode")
- **No silent mock fallback** — live backend failures remain honest errors
- Mock mode verified end-to-end with no backend running
- Live mode verified end-to-end with backend offline — honest ErrorState + retry, zero mock data leak

## Responsive Behavior

| Breakpoint | Behavior |
|---|---|
| Desktop (`lg+`) | Fixed sidebar (`w-64`), header `h-12`, page container `max-w-7xl`, 5-col stat grid |
| Tablet (`sm`–`lg`) | Sidebar collapses to Sheet drawer, 3-col stat grid |
| Mobile (below `sm`) | Sheet drawer full height, single-col stat grid, stacked document rows |
| Overflow | `min-w-0` on flex containers, `truncate` on long text, no horizontal overflow |

## Accessibility

- Skip-to-content link preserved
- Semantic HTML: `<header>`, `<nav>`, `<main>`
- Focus-visible rings on all interactive elements
- `aria-label` on icon buttons, `aria-current` on active nav links
- `role="status"` on loading indicators
- Status chips convey meaning via text labels + colored dots (not color alone)
- WCAG AA contrast targets via oklch token choices
- Theme toggle has accessible `aria-label` announcing target theme
- Keyboard-navigable: all buttons/links natively focusable

## Verification Results

All checks executed against `frontend/app`, 5 November 2026:

| Check | Result |
|---|---|
| `npm run typecheck` (strict) | ✅ 0 errors |
| `npm run test` (Vitest, node environment) | ✅ 4 files, 40 tests passed |
| `npm run lint` (oxlint) | ✅ 0 findings |
| `npm run build` (production) | ✅ built ~283 ms |
| Mock mode E2E (headless Chrome, no backend) | ✅ "Mock data mode" badge; dashboard renders fixture corpus; no error state; no fixture data modified |
| Live mode E2E (headless Chrome, backend offline) | ✅ "Live API mode" badge; honest ErrorState + retry; zero fabricated counts; no mock data leak |
| Routes verified at desktop width | ✅ `/`, `/documents`, `/documents/:id`, `/assistant`, `*` (404) |
| Responsive classes present | ✅ `lg:block`, `sm:`, `lg:` breakpoint classes in DOM |
| Git scope | ✅ Changes only under `frontend/` |

## Remaining Limitations

1. Dark theme was verified through token definitions and code inspection; interactive theme switching was not exercised in headless Chrome (requires user interaction with ThemeToggle).
2. Tablet and mobile breakpoints were verified through responsive class presence in DOM; physical device testing was not performed.
3. Document library, document detail, and assistant pages are visual foundations only — no data fetching or Z03/Z04 workflows implemented.
4. The pre-existing >500 kB chunk size warning from Vite/Rolldown is deferred to a future phase.

## Files Changed

**Created (9):**
- `frontend/app/src/components/shared/theme-context.ts`
- `frontend/app/src/components/shared/theme-provider.tsx`
- `frontend/app/src/components/shared/use-theme.ts`
- `frontend/app/src/components/shared/theme-toggle.tsx`
- `frontend/app/src/components/shared/page-container.tsx`
- `frontend/app/src/components/shared/stat-card.tsx`
- `frontend/app/src/components/shared/document-type-icon.tsx`
- `frontend/app/src/features/documents/components/document-row.tsx`
- `frontend/app/src/features/documents/components/data-table.tsx`

**Modified (13):**
- `frontend/app/src/styles/tokens.css` — deep navy/slate primary, restrained blue accent, status tokens, shadow tokens, light/dark variants
- `frontend/app/src/components/layout/nav-config.ts` — fixed active-state `end` props, removed placeholder concept
- `frontend/app/src/components/layout/app-sidebar.tsx` — removed soon badges + theme toggle, compact mode indicator
- `frontend/app/src/components/layout/app-header.tsx` — added theme toggle, compact breadcrumbs
- `frontend/app/src/app/layouts/root-layout.tsx` — uses `PageContainer` for consistent page layout
- `frontend/app/src/components/shared/page-header.tsx` — consistent hierarchy
- `frontend/app/src/components/shared/stat-card.tsx` — compact sizing, prominent value
- `frontend/app/src/components/shared/empty-state.tsx` — consistent padding
- `frontend/app/src/features/dashboard/components/dashboard-page.tsx` — 5 accurate metrics, mutually exclusive states
- `frontend/app/src/features/documents/components/document-library-page.tsx` — table header foundation + empty state
- `frontend/app/src/features/documents/components/document-detail-page.tsx` — removed all fabricated data
- `frontend/app/src/features/documents/components/data-table.tsx` — header row only, no skeleton body
- `frontend/app/src/features/assistant/components/assistant-page.tsx` — removed duplicates + fabricated data

**Deleted:** none

**Environment:**
- `frontend/app/.env` — commented out `VITE_DATA_MODE=mock` so `live` is the default

**Documentation:**
- `frontend/docs/UI_REDESIGN_CHANGELOG.md` — this report
