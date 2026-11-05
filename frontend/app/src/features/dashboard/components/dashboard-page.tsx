import { Link } from "react-router-dom"
import { ArrowRightIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { PageHeader } from "@/components/shared/page-header"
import { EmptyState } from "@/components/shared/empty-state"
import { ErrorState } from "@/components/shared/error-state"
import { StatusBadge } from "@/components/shared/status-badge"
import { DocumentTypeIcon } from "@/components/shared/document-type-icon"
import { StatCard } from "@/components/shared/stat-card"
import { useDashboardOverview } from "@/features/dashboard/hooks/use-dashboard-overview"
import type { DocumentState } from "@/features/documents/types/document.types"

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
})

const statusOrder: DocumentState[] = ["complete", "processing", "queued", "failed"]

const statusCardCaption: Record<DocumentState, string> = {
  complete: "Ready to answer queries (terminal).",
  processing: "Ingestion running (non-terminal).",
  queued: "Waiting for processing (non-terminal).",
  failed: "Ingestion stopped (terminal).",
}

function StatsSkeleton() {
  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 lg:grid-cols-5">
      {[...statusOrder, "total"].map((key) => (
        <Card key={key}>
          <CardHeader>
            <CardTitle className="text-xs font-medium text-muted-foreground">
              {key === "total" ? "Total" : key[0].toUpperCase() + key.slice(1)}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <Skeleton className="h-6 w-20" />
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

function RecentDocumentsSkeleton() {
  return (
    <Card>
      <CardContent className="flex flex-col gap-2 p-4">
        <Skeleton className="h-4 w-40" />
        {[0, 1, 2, 3, 4].map((row) => (
          <Skeleton key={row} className="h-8 w-full" />
        ))}
      </CardContent>
    </Card>
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
  const overview = useDashboardOverview()
  const data = overview.data

  return (
    <>
      <PageHeader
        title="Overview"
        description="Monitor the state of your organization's knowledge base."
        actions={
          <Button asChild variant="outline" size="sm">
            <Link to="/documents">
              View all documents
              <ArrowRightIcon className="ml-1 size-4" aria-hidden="true" />
            </Link>
          </Button>
        }
      />

      {overview.isLoading ? (
        <>
          <StatsSkeleton />
          <RecentDocumentsSkeleton />
        </>
      ) : overview.isError ? (
        <ErrorState
          error={overview.error}
          onRetry={() => {
            overview.refetch()
          }}
        />
      ) : data ? (
        <>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
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

          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold">
                {data.total.toLocaleString()} document
                {data.total === 1 ? "" : "s"} accessible
              </CardTitle>
              <CardDescription>
                {data.capped
                  ? `Status breakdown covers the first ${data.scanned} documents; total reflects every accessible document.`
                  : "Status breakdown covers every accessible document returned by the backend."}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {data.total === 0 ? (
                <EmptyState
                  title="No documents yet"
                  description="Documents uploaded through the backend appear here once they are visible to the server-side demo actor."
                />
              ) : (
                <>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-border">
                          <th className="px-3 py-2 text-left text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                            Type
                          </th>
                          <th className="px-3 py-2 text-left text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                            Title
                          </th>
                          <th className="px-3 py-2 text-left text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                            Status
                          </th>
                          <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                            Chunks
                          </th>
                          <th className="px-3 py-2 text-right text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
                            Created
                          </th>
                        </tr>
                      </thead>
                      <tbody>
                        {data.recent.map((document) => (
                          <tr
                            key={document.id}
                            className="border-b border-border last:border-0 hover:bg-muted/50"
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
                  <div className="mt-3">
                    <Button asChild variant="ghost" size="sm">
                      <Link to="/documents">
                        View all
                        <ArrowRightIcon className="ml-1 size-4" aria-hidden="true" />
                      </Link>
                    </Button>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </>
      ) : null}
    </>
  )
}
