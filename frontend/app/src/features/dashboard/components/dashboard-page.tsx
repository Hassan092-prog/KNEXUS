import { Link } from "react-router-dom"
import { ArrowRightIcon, UploadIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { PageHeader } from "@/components/shared/page-header"
import { EmptyState } from "@/components/shared/empty-state"
import { ErrorState } from "@/components/shared/error-state"
import { StatusBadge } from "@/components/shared/status-badge"
import { DocumentTypeIcon } from "@/components/shared/document-type-icon"
import { StatCard } from "@/components/shared/stat-card"
import { useDashboardOverview } from "@/features/dashboard/hooks/use-dashboard-overview"
import { UploadDialog } from "@/features/documents/components/upload-dialog"
import { DocumentCard } from "@/features/documents/components/document-card"
import type { DocumentState } from "@/features/documents/types/document.types"

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
})

const statusOrder: DocumentState[] = ["complete", "processing", "queued", "failed"]

const statusCardCaption: Record<DocumentState, string> = {
  complete: "Ready for knowledge queries",
  processing: "Currently being processed",
  queued: "Waiting to be processed",
  failed: "Requires attention",
}

function StatsSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 lg:grid-cols-5">
      {[...statusOrder, "total"].map((key) => (
        <StatCard
          key={key}
          value={<Skeleton className="h-6 w-20" />}
          label={key === "total" ? "Total documents" : key[0].toUpperCase() + key.slice(1)}
          caption="—"
        />
      ))}
    </div>
  )
}

function RecentDocumentsSkeleton() {
  return (
    <div className="mt-10 rounded-lg border border-border bg-card p-5">
      <div className="flex items-start justify-between gap-2 mb-4">
        <p className="text-xs font-medium uppercase tracking-wider text-muted-foreground">
          Recent documents
        </p>
        <Skeleton className="h-4 w-24" />
      </div>
      <div className="flex flex-col gap-3">
        {[0, 1, 2, 3, 4].map((row) => (
          <div key={row} className="flex gap-4">
            <Skeleton className="h-8 w-12 shrink-0 rounded-lg" />
            <Skeleton className="h-4 w-32" />
            <Skeleton className="h-4 w-20" />
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-20" />
          </div>
        ))}
      </div>
    </div>
  )
}

/**
 * Real-data overview: every number is derived from `GET /api/v1/documents`
 * (pagination meta + page payloads). Nothing here invents analytics.
 * `capped` is honored so counts never imply complete corpus coverage when
 * only a partial scan has been retrieved.
 *
 * Loading, error, and populated states are mutually exclusive.
 */
export function DashboardPage() {
  const { overview, isLoading, isError, error, refetch } = useDashboardOverview()
  const data = overview

  return (
    <>
      <PageHeader
        title="Overview"
        description="Monitor the state of your organization's knowledge base."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <UploadDialog
              trigger={
                <Button size="sm">
                  <UploadIcon className="size-4" aria-hidden="true" />
                  Upload document
                </Button>
              }
            />
            <Button asChild variant="outline" size="sm">
              <Link to="/assistant">
                Ask the assistant
                <ArrowRightIcon className="ml-1 size-4" aria-hidden="true" />
              </Link>
            </Button>
            <Button asChild variant="outline" size="sm">
              <Link to="/documents">View all documents</Link>
            </Button>
          </div>
        }
      />

      {isLoading ? (
        <>
          <StatsSkeleton />
          <RecentDocumentsSkeleton />
        </>
      ) : isError ? (
        <ErrorState
          error={error}
          onRetry={() => {
            void refetch()
          }}
        />
      ) : data ? (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 lg:grid-cols-5">
            <StatCard
              value={data.total.toLocaleString()}
              label="Total documents"
              caption="Accessible documents"
            />
            {statusOrder.map((status) => (
              <StatCard
                key={status}
                value={data.statusCounts[status].toLocaleString()}
                label={status[0].toUpperCase() + status.slice(1)}
                caption={statusCardCaption[status]}
              />
            ))}
          </div>

          {data.capped ? (
            <p className="mt-3 text-xs text-muted-foreground" role="status">
              Status counts cover the {data.scanned.toLocaleString()} most recent of {data.total.toLocaleString()} documents
              (scan limit); the total remains the complete backend count.
            </p>
          ) : null}

          <section className="mt-10">
            <div className="flex items-start justify-between gap-3 mb-4">
              <div>
                <h2 className="text-sm font-semibold tracking-tight text-foreground">
                  Recent documents
                </h2>
                <p className="mt-1 text-xs text-muted-foreground">
                  Newest documents first. Click a document to view its details.
                </p>
              </div>
            </div>

            {data.total === 0 ? (
              <EmptyState
                variant="surface"
                title="No documents yet"
                description="Documents uploaded through the backend appear here once they are visible to the server-side demo actor."
                action={
                  <Button asChild variant="outline" size="sm">
                    <Link to="/documents">Open the document library</Link>
                  </Button>
                }
              />
            ) : (
              <>
                <div className="hidden overflow-hidden rounded-lg border border-border bg-card lg:block">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="bg-muted/50 border-b border-border">
                        <th className="w-14 px-3 py-2.5 text-left text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                          Type
                        </th>
                        <th className="px-3 py-2.5 text-left text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                          Title
                        </th>
                        <th className="w-28 px-3 py-2.5 text-left text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                          Status
                        </th>
                        <th className="w-16 px-3 py-2.5 text-right text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                          Chunks
                        </th>
                        <th className="w-40 px-3 py-2.5 text-right text-[10px] font-medium uppercase tracking-wider text-muted-foreground">
                          Created
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.recent.map((document) => (
                        <tr
                          key={document.id}
                          className="border-b border-border last:border-0 hover:bg-muted/50 transition-colors"
                        >
                          <td className="px-3 py-3">
                            <DocumentTypeIcon sourceType={document.source_type} />
                          </td>
                          <td className="px-3 py-3">
                            <Link
                              to={`/documents/${document.id}`}
                              className="font-medium text-foreground outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring"
                            >
                              {document.title}
                            </Link>
                            <p className="mt-0.5 text-xs text-muted-foreground">
                              {document.allowed_roles.join(", ")}
                            </p>
                          </td>
                          <td className="px-3 py-3">
                            <StatusBadge status={document.status} />
                          </td>
                          <td className="px-3 py-3 text-right tabular-nums text-xs text-muted-foreground">
                            {document.chunk_count}
                          </td>
                          <td className="px-3 py-3 text-right tabular-nums text-xs text-muted-foreground">
                            {dateFormatter.format(new Date(document.created_at))}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="grid gap-3 lg:hidden">
                  {data.recent.map((document) => (
                    <DocumentCard key={document.id} document={document} />
                  ))}
                </div>
              </>
            )}
          </section>
        </>
      ) : null}
    </>
  )
}
