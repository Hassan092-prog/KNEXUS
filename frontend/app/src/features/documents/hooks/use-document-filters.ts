import { useCallback, useMemo, useState } from "react"

import type {
  DocumentRole,
  DocumentSourceType,
  DocumentState,
  DocumentSummary,
} from "@/features/documents/types/document.types"

/**
 * Filter model for the document library. The backend exposes no search or
 * filter route, so filters are a frontend concern applied over the scanned
 * accessible collection.
 */
export interface DocumentFilters {
  query: string
  status: DocumentState | "all"
  sourceType: DocumentSourceType | "all"
  role: DocumentRole | "all"
}

export const DEFAULT_FILTERS: DocumentFilters = {
  query: "",
  status: "all",
  sourceType: "all",
  role: "all",
}

export function hasActiveFilters(filters: DocumentFilters): boolean {
  return (
    filters.query.trim().length > 0 ||
    filters.status !== "all" ||
    filters.sourceType !== "all" ||
    filters.role !== "all"
  )
}

export function matchesFilters(document: DocumentSummary, filters: DocumentFilters): boolean {
  const query = filters.query.trim().toLowerCase()
  const matchesQuery = query === "" || document.title.toLowerCase().includes(query)
  const matchesStatus = filters.status === "all" || document.status === filters.status
  const matchesType = filters.sourceType === "all" || document.source_type === filters.sourceType
  const matchesRole = filters.role === "all" || document.allowed_roles.includes(filters.role)
  return matchesQuery && matchesStatus && matchesType && matchesRole
}

export interface UseDocumentFiltersResult {
  filters: DocumentFilters
  updateFilters: (patch: Partial<DocumentFilters>) => void
  setFilters: (filters: DocumentFilters) => void
  clearFilters: () => void
  filtered: (documents: DocumentSummary[]) => DocumentSummary[]
  isFiltered: boolean
}

/** Local UI state for library filtering (transient interaction, not server state). */
export function useDocumentFilters(): UseDocumentFiltersResult {
  const [filters, setFiltersState] = useState<DocumentFilters>(DEFAULT_FILTERS)

  const updateFilters = useCallback((patch: Partial<DocumentFilters>) => {
    setFiltersState((current) => ({ ...current, ...patch }))
  }, [])

  const setFilters = useCallback((current: DocumentFilters) => {
    setFiltersState(current)
  }, [])

  const clearFilters = useCallback(() => {
    setFiltersState(DEFAULT_FILTERS)
  }, [])

  const filterDocuments = useCallback(
    (documents: DocumentSummary[]) => documents.filter((document) => matchesFilters(document, filters)),
    [filters],
  )

  const isFiltered = hasActiveFilters(filters)

  return useMemo(
    () => ({ filters, updateFilters, setFilters, clearFilters, filtered: filterDocuments, isFiltered }),
    [filters, updateFilters, setFilters, clearFilters, filterDocuments, isFiltered],
  )
}
