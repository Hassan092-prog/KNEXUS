import { XIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { DOCUMENT_ROLES } from "@/lib/api/contracts"
import type { DocumentState, DocumentSourceType } from "@/features/documents/types/document.types"
import { ROLE_LABELS, STATUS_LABELS, TYPE_LABELS } from "@/features/documents/document-labels"
import type { DocumentFilters } from "@/features/documents/hooks/use-document-filters"

const STATUS_OPTIONS: DocumentState[] = ["queued", "processing", "complete", "failed"]

/**
 * Search + filter controls for the document library. Presentational: values
 * and change handlers arrive typed from the owning page.
 */
export function DocumentFiltersBar({
  filters,
  onChange,
  onClear,
}: {
  filters: DocumentFilters
  onChange: (patch: Partial<DocumentFilters>) => void
  onClear: () => void
}) {
  const hasAnyValue =
    filters.query.trim().length > 0 || filters.status !== "all" || filters.sourceType !== "all" || filters.role !== "all"

  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
      <label className="sr-only" htmlFor="document-search">
        Search documents by title
      </label>
      <Input
        id="document-search"
        type="search"
        value={filters.query}
        onChange={(event) => onChange({ query: event.target.value })}
        placeholder="Search by title…"
        className="h-8 w-full sm:max-w-64"
      />

      <div className="flex flex-wrap gap-2">
        <label className="sr-only" htmlFor="filter-status">
          Filter by processing status
        </label>
        <Select
          value={filters.status}
          onValueChange={(value) => onChange({ status: value as DocumentFilters["status"] })}
        >
          <SelectTrigger id="filter-status" size="sm" className="w-32">
            <SelectValue placeholder="Status" aria-label="Filter by processing status" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All status</SelectItem>
            {STATUS_OPTIONS.map((status) => (
              <SelectItem key={status} value={status}>
                {STATUS_LABELS[status]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <label className="sr-only" htmlFor="filter-source-type">
          Filter by file type
        </label>
        <Select
          value={filters.sourceType}
          onValueChange={(value) => onChange({ sourceType: value as DocumentFilters["sourceType"] })}
        >
          <SelectTrigger id="filter-source-type" size="sm" className="w-28">
            <SelectValue placeholder="File type" aria-label="Filter by file type" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All types</SelectItem>
            {(Object.keys(TYPE_LABELS) as DocumentSourceType[]).map((sourceType) => (
              <SelectItem key={sourceType} value={sourceType}>
                {TYPE_LABELS[sourceType]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <label className="sr-only" htmlFor="filter-role">
          Filter by allowed role
        </label>
        <Select value={filters.role} onValueChange={(value) => onChange({ role: value as DocumentFilters["role"] })}>
          <SelectTrigger id="filter-role" size="sm" className="w-32">
            <SelectValue placeholder="Role" aria-label="Filter by allowed role" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All roles</SelectItem>
            {DOCUMENT_ROLES.map((role) => (
              <SelectItem key={role} value={role}>
                {ROLE_LABELS[role]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {hasAnyValue ? (
        <Button
          variant="ghost"
          size="sm"
          onClick={onClear}
          className="shrink-0 text-muted-foreground"
        >
          <XIcon className="size-3.5" aria-hidden="true" />
          Clear
        </Button>
      ) : null}
    </div>
  )
}
