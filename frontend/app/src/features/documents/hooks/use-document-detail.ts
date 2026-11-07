import { useQuery } from "@tanstack/react-query"

import { getDocumentApi } from "@/lib/api"
import { documentKeys } from "@/features/documents/hooks/query-keys"
import { ApiError } from "@/lib/api/error"

/**
 * Document detail for a route param. A `NOT_FOUND` failure (missing,
 * cross-tenant or deleted document) surfaces through the normalized error,
 * giving the page a concrete "back to library" path instead of guessing.
 */
export function useDocumentDetail(documentId: string) {
  const query = useQuery({
    queryKey: documentKeys.detail(documentId),
    queryFn: () => getDocumentApi().getDocument(documentId),
    staleTime: 30_000,
    retry: false,
  })

  const notFound = query.error instanceof ApiError && query.error.code === "NOT_FOUND"

  return {
    detail: query.data,
    isLoading: query.isPending,
    isError: query.isError,
    error: query.error,
    notFound,
    refetch: query.refetch,
  }
}
