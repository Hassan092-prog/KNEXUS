import { useQuery } from "@tanstack/react-query"

import { getDocumentApi } from "@/lib/api"
import type { DocumentSummary } from "@/features/documents/types/document.types"
import { documentKeys } from "@/features/documents/hooks/query-keys"

/**
 * Retrieves the caller's accessible documents by scanning `GET /documents`
 * (`limit`/`offset`, API maximum of 100 per page). The backend exposes no
 * search/aggregate routes, so the library table, its filters, and the
 * dashboard counters all work over this one shared query.
 *
 * The scan is capped at MAX_SCAN_PAGES pages. When the cap is reached,
 * `total` still comes from the backend pagination meta but `documents`
 * covers only the scanned subset (`capped: true` lets the UI say so instead
 * of presenting an incomplete count as the full collection).
 */

export const SCAN_PAGE_SIZE = 100
const MAX_SCAN_PAGES = 10

export interface DocumentCollection {
  /** Scanned documents, newest first (backend list ordering). */
  documents: DocumentSummary[]
  /** From backend pagination meta — reflects every accessible document. */
  total: number
  /** How many documents were actually scanned. */
  scanned: number
  /** True when the scan stopped at its page cap. */
  capped: boolean
}

async function fetchDocumentCollection(): Promise<DocumentCollection> {
  const documentApi = getDocumentApi()
  let documents: DocumentSummary[] = []
  let total = 0
  let capped = false

  for (let page = 0; page < MAX_SCAN_PAGES; page += 1) {
    const list = await documentApi.listDocuments({ limit: SCAN_PAGE_SIZE, offset: page * SCAN_PAGE_SIZE })
    total = list.meta.total
    documents = [...documents, ...list.data]
    if (list.data.length < SCAN_PAGE_SIZE || documents.length >= total) {
      return { documents, total, scanned: documents.length, capped }
    }
  }

  return { documents, total, scanned: documents.length, capped: true }
}

/**
 * Shared server-state query for the accessible document collection:
 * cached, honest about partial scans, and never silently retried (failures
 * surface in the ErrorState with explicit retry).
 */
export function useDocumentCollection() {
  return useQuery({
    queryKey: documentKeys.scan(),
    queryFn: fetchDocumentCollection,
    staleTime: 30_000,
    retry: false,
  })
}
