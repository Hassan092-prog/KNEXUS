import { useEffect, useRef } from "react"
import { useQuery, useQueryClient } from "@tanstack/react-query"

import { getDocumentApi } from "@/lib/api"
import type { DocumentStatusResponse } from "@/features/documents/types/document.types"
import { documentKeys } from "@/features/documents/hooks/query-keys"

/**
 * Persisted processing-status query with controlled polling.
 *
 * - Polls only while `queued`/`processing` (TanStack stops the interval the
 *   moment the terminal status arrives, and not while the tab is hidden).
 * - On the first observation of a terminal status, the detail query and the
 *   collection scan are invalidated so every surface reflects the outcome.
 * - `terminal`/`failureCode`/`failureMessage` are returned verbatim from the
 *   backend; the UI never fabricates progress for unknown totals.
 */

const ACTIVE_POLL_MS = 4_000

function isTerminal(status: DocumentStatusResponse["status"]): boolean {
  return status === "complete" || status === "failed"
}

export function useDocumentStatus(documentId: string) {
  const queryClient = useQueryClient()
  /** Last terminal status we already invalidated derived queries for. */
  const lastInvalidateRef = useRef<string | null>(null)

  const query = useQuery({
    queryKey: documentKeys.status(documentId),
    queryFn: () => getDocumentApi().getDocumentStatus(documentId),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      const hasError = query.state.error instanceof Error
      if (status !== undefined && isTerminal(status)) return false
      // Stop polling if the query has encountered an error.
      if (hasError) return false
      return ACTIVE_POLL_MS
    },
    refetchIntervalInBackground: false,
    retry: false,
    // The status query itself is never stale-cached longer than the poll loop;
    // keep it fresh so a remount reuses a recent terminal result.
    staleTime: 5_000,
  })

  const { data } = query
  useEffect(() => {
    if (!data || !isTerminal(data.status)) {
      lastInvalidateRef.current = null
      return
    }
    const terminalKey = `${data.status}:${data.failure_code}`
    if (lastInvalidateRef.current === terminalKey) return // already refreshed
    lastInvalidateRef.current = terminalKey
    void queryClient.invalidateQueries({ queryKey: documentKeys.detail(documentId) })
    void queryClient.invalidateQueries({ queryKey: documentKeys.scan() })
  }, [data, documentId, queryClient])

  return {
    status: query.data,
    isLoading: query.isPending,
    isError: query.isError,
    error: query.error,
    isTerminal: data !== undefined && isTerminal(data.status),
    refetch: query.refetch,
  }
}
