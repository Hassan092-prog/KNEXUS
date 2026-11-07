import { useMemo } from "react"

import { useDocumentCollection } from "@/features/documents/hooks/use-document-collection"
import type { DocumentState, DocumentSummary } from "@/features/documents/types/document.types"

/**
 * Dashboard overview derived exclusively from `GET /api/v1/documents`
 * (shared collection scan + pagination meta). The backend exposes no
 * aggregate analytics route, so counters accumulate over the scanned pages.
 *
 * `capped` is honored: total remains the real backend total while per-status
 * counts cover only scanned documents, so the UI can disclose partial
 * coverage instead of implying exact totals.
 */
export interface DashboardOverview {
  total: number
  statusCounts: Record<DocumentState, number>
  /** Newest documents (list endpoint is ordered by `created_at desc`). */
  recent: DocumentSummary[]
  scanned: number
  capped: boolean
}

const RECENT_LIMIT = 5

function emptyStatusCounts(): Record<DocumentState, number> {
  return { queued: 0, processing: 0, complete: 0, failed: 0 }
}

function useDashboardOverviewState(collection: ReturnType<typeof useDocumentCollection>) {
  return useMemo(() => {
    const data = collection.data
    if (data === undefined) return undefined
    const statusCounts = emptyStatusCounts()
    for (const document of data.documents) {
      statusCounts[document.status] += 1
    }
    return {
      total: data.total,
      statusCounts,
      recent: data.documents.slice(0, RECENT_LIMIT),
      scanned: data.scanned,
      capped: data.capped,
    } satisfies DashboardOverview
  }, [collection.data])
}

export function useDashboardOverview() {
  const collection = useDocumentCollection()
  const overview = useDashboardOverviewState(collection)

  return {
    overview,
    isLoading: collection.isPending,
    isError: collection.isError,
    error: collection.error,
    refetch: collection.refetch,
  }
}
