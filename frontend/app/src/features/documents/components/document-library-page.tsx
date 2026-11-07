import { useEffect, useMemo, useState } from "react"
import { Link } from "react-router-dom"
import { LibraryBigIcon, UploadIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { PageHeader } from "@/components/shared/page-header"
import { EmptyState } from "@/components/shared/empty-state"
import { ErrorState } from "@/components/shared/error-state"
import { TablePagination } from "@/components/shared/table-pagination"
import { DocumentFiltersBar } from "@/features/documents/components/document-filters-bar"
import { DocumentsTable } from "@/features/documents/components/documents-table"
import { DocumentCard } from "@/features/documents/components/document-card"
import { UploadDialog } from "@/features/documents/components/upload-dialog"
import { useDocumentCollection } from "@/features/documents/hooks/use-document-collection"
import { useDocumentFilters } from "@/features/documents/hooks/use-document-filters"

const LIBRARY_PAGE_SIZE = 20
const LG_BREAKPOINT = 1024

/**
 * Document library over `GET /api/v1/documents`.
 *
 * Data handling: the shared collection scan powers the full-accessible-table
 * search, filters (frontend-side over scanned records — the backend exposes no
 * search route), and client-side pagination over the filtered slice. Partial
 * scans are disclosed (`capped`), never presented as complete collections.
 */
export function DocumentLibraryPage() {
  const collection = useDocumentCollection()
  const { filters, updateFilters, clearFilters, filtered, isFiltered } = useDocumentFilters()

  const [page, setPage] = useState(1)
  const [isLg, setIsLg] = useState(() => typeof window !== "undefined" ? window.innerWidth >= LG_BREAKPOINT : false)

  useEffect(() => {
    const handleResize = () => setIsLg(window.innerWidth >= LG_BREAKPOINT)
    window.addEventListener("resize", handleResize)
    return () => window.removeEventListener("resize", handleResize)
  }, [])
  // Reset to the first page whenever the filter criteria change (state
  // adjustment during render — avoids a cascading setState effect).
  const [lastFilters, setLastFilters] = useState(filters)
  if (lastFilters !== filters) {
    setLastFilters(filters)
    setPage(1)
  }

  const filteredDocuments = useMemo(() => filtered(collection.data?.documents ?? []), [filtered, collection.data])
  const pageCount = Math.max(1, Math.ceil(filteredDocuments.length / LIBRARY_PAGE_SIZE))
  const currentPage = Math.min(page, pageCount)
  const pageSlice = filteredDocuments.slice((currentPage - 1) * LIBRARY_PAGE_SIZE, currentPage * LIBRARY_PAGE_SIZE)

  const data = collection.data

  return (
    <>
      <PageHeader
        title="Documents"
        description="Manage documents available to your organization's knowledge base."
        actions={
          <UploadDialog
            trigger={
              <Button size="sm">
                <UploadIcon className="size-4" aria-hidden="true" />
                Upload document
              </Button>
            }
          />
        }
      />

      {collection.isPending ? (
        <LibrarySkeleton />
      ) : collection.isError ? (
        <ErrorState
          error={collection.error}
          onRetry={() => {
            void collection.refetch()
          }}
        />
      ) : data !== undefined && data.total === 0 ? (
        <EmptyState
          icon={LibraryBigIcon}
          title="No documents yet"
          description="Upload a PDF or DOCX document to make its content available for knowledge queries."
          action={
            <UploadDialog
              open={undefined}
              trigger={
                <Button size="sm">
                  <UploadIcon className="size-4" aria-hidden="true" />
                  Upload your first document
                </Button>
              }
            />
          }
        />
      ) : (
        <>
          <DocumentFiltersBar filters={filters} onChange={updateFilters} onClear={clearFilters} />

          {isFiltered ? (
            <p className="mt-3 text-xs text-muted-foreground" role="status">
              {filteredDocuments.length === 0
                ? "No documents match the current search."
                : `${filteredDocuments.length} of ${(data?.scanned ?? 0).toLocaleString()} scanned documents match.`}
            </p>
          ) : data !== undefined && data.capped ? (
            <p className="mt-3 text-xs text-muted-foreground" role="status">
              Showing the {data.scanned.toLocaleString()} most recent of {data.total.toLocaleString()} accessible documents.
            </p>
          ) : null}

          <div className="mt-2 rounded-lg border border-border bg-card p-1 sm:p-2">
            {filteredDocuments.length === 0 ? (
              <EmptyState
                variant="surface"
                icon={LibraryBigIcon}
                title="No documents match your search"
                description="Adjust the search term or clear the filters to see the full accessible library."
                action={
                  <Button variant="outline" size="sm" onClick={clearFilters}>
                    Clear filters
                  </Button>
                }
              />
            ) : (
              <>
                {isLg ? (
                  <DocumentsTable documents={pageSlice} caption="Accessible documents" />
                ) : (
                  <div>
                    {pageSlice.map((document) => (
                      <DocumentCard key={document.id} document={document} />
                    ))}
                  </div>
                )}
                {pageCount > 1 ? (
                  <TablePagination page={currentPage} pageCount={pageCount} onPageChange={setPage} />
                ) : (
                  <p className="px-2 pb-2 pt-1 text-xs text-muted-foreground">
                    Page 1 · {filteredDocuments.length} {filteredDocuments.length === 1 ? "document" : "documents"}
                  </p>
                )}
              </>
            )}
          </div>

          <p className="mt-2 text-xs text-muted-foreground">
            Documents visible to the server-side actor.{" "}
            <Link to="/assistant" className="text-foreground underline outline-none hover:no-underline focus-visible:ring-2 focus-visible:ring-ring">
              Ask the assistant
            </Link>{" "}
            a question to search their content.
          </p>
        </>
      )}
    </>
  )
}

function LibrarySkeleton() {
  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-2">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-8 w-32" />
        <Skeleton className="h-8 w-28" />
      </div>
      <div className="rounded-lg border border-border bg-card p-1 sm:p-2">
        {[1, 2, 3, 4, 5, 6].map((row) => (
          <div key={row} className="flex items-center gap-4 px-3 py-3">
            <Skeleton className="size-8 rounded-md" />
            <Skeleton className="h-4 w-64" />
            <Skeleton className="h-5 w-24" />
            <Skeleton className="ml-auto h-4 w-20" />
          </div>
        ))}
      </div>
    </div>
  )
}
