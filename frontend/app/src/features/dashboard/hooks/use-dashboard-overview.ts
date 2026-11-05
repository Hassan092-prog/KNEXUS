import { useQuery } from "@tanstack/react-query"

import { getDocumentApi } from "@/lib/api"
import type { DocumentState, DocumentSummary } from "@/features/documents/types/document.types"

/**
 * Live dashboard counters derived exclusively from `GET /api/v1/documents`
 * pagination meta and page payloads. The backend exposes no aggregate
 * analytics route, so counts are accumulated by paging through the list.
 *
 * The scan is capped at `MAX_PAGES` pages; when capped, `total` still comes
 * from the backend meta but per-status counts reflect only the scanned pages
 * (`capped: true` lets the UI say so instead of implying full coverage).
 */

const PAGE_SIZE = 100
const MAX_PAGES = 5

export interface DashboardOverview {
  /** From backend pagination meta — reflects every accessible document. */
  total: number
  statusCounts: Record<DocumentState, number>
  /** Newest documents (list endpoint is ordered by `created_at desc`). */
  recent: DocumentSummary[]
  /** How many documents the status counts actually scanned. */
  scanned: number
  capped: boolean
}

function emptyStatusCounts(): Record<DocumentState, number> {
  return { queued: 0, processing: 0, complete: 0, failed: 0 }
}

async function fetchOverview(): Promise<DashboardOverview> {
  const statusCounts = emptyStatusCounts()
  let offset = 0
  let total = 0
  let recent: DocumentSummary[] = []

  for (let page = 0; page < MAX_PAGES; page += 1) {
    const list = await getDocumentApi().listDocuments({ limit: PAGE_SIZE, offset })
    total = list.meta.total
    for (const document of list.data) {
      statusCounts[document.status] += 1
    }
    recent = [...recent, ...list.data]
    offset += PAGE_SIZE
    if (list.data.length < PAGE_SIZE || offset >= total) {
      return { total, statusCounts, recent: recent.slice(0, 5), scanned: offset, capped: false }
    }
  }

  return {
    total,
    statusCounts,
    recent: recent.slice(0, 5),
    scanned: offset,
    capped: true,
  }
}

export function useDashboardOverview() {
  return useQuery({
    queryKey: ["documents", "overview"] as const,
    queryFn: fetchOverview,
    // Surfacing backend failures (e.g. offline dev backend) keeps the UI honest.
    retry: false,
  })
}
