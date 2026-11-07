import { Link, useParams } from "react-router-dom"
import { ArrowLeftIcon, LibraryIcon } from "lucide-react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Separator } from "@/components/ui/separator"
import { Skeleton } from "@/components/ui/skeleton"
import { PageHeader } from "@/components/shared/page-header"
import { EmptyState } from "@/components/shared/empty-state"
import { ErrorState } from "@/components/shared/error-state"
import { CopyIdButton } from "@/components/shared/copy-id-button"
import { DocumentTypeIcon } from "@/components/shared/document-type-icon"
import { ProcessingPanel } from "@/features/documents/components/processing-panel"
import { useDocumentDetail } from "@/features/documents/hooks/use-document-detail"
import { useDocumentStatus } from "@/features/documents/hooks/use-document-status"
import { formatDateTime } from "@/lib/utils/format"
import { TYPE_LABELS } from "@/features/documents/document-labels"

/**
 * Document details + processing status.
 *
 * Data: `GET /documents/{id}` for information and `GET /documents/{id}/status`
 * polled by `useDocumentStatus` only while queued/processing. Invalid or
 * unknown IDs surface the backend's `NOT_FOUND` envelope with a path back to
 * the library.
 */
export function DocumentDetailPage() {
  const { documentId } = useParams<{ documentId: string }>()
  if (documentId === undefined) {
    throw new Error("Document detail route requires a documentId param.")
  }

  const detail = useDocumentDetail(documentId)
  const status = useDocumentStatus(documentId)
  const document = detail.detail

  return (
    <div>
      <Button asChild variant="outline" size="sm" className="mb-6 -ml-1">
        <Link to="/documents">
          <ArrowLeftIcon className="size-4" aria-hidden="true" />
          Documents
        </Link>
      </Button>

      <PageHeader
        title="Document details"
        description="Information about this document and its processing state."
      />

      {detail.isLoading ? (
        <DetailSkeleton />
      ) : detail.isError ? (
        detail.notFound ? (
          <EmptyState
            icon={LibraryIcon}
            title="Document not found"
            description="This document does not exist, is not visible to this actor, or has been removed."
            action={
              <Button asChild variant="outline" size="sm">
                <Link to="/documents">Back to the document library</Link>
              </Button>
            }
          />
        ) : (
          <ErrorState
            error={detail.error}
            onRetry={() => {
              void detail.refetch()
            }}
          />
        )
      ) : document !== undefined ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="flex flex-col gap-5 p-5">
            <div className="flex items-start gap-3">
              <DocumentTypeIcon sourceType={document.source_type} className="size-9" />
              <div className="min-w-0">
                <h2 className="break-words font-heading text-base font-semibold tracking-tight text-foreground">
                  {document.title}
                </h2>
                <p className="mt-0.5 text-xs text-muted-foreground">{TYPE_LABELS[document.source_type]}</p>
              </div>
            </div>

            <Separator />

            <dl className="grid grid-cols-1 gap-x-6 gap-y-3 text-xs sm:grid-cols-2">
              <InfoRow label="Chunk count" value={<span className="tabular-nums">{document.chunk_count}</span>} />
              <InfoRow
                label="Created"
                value={
                  <span className="tabular-nums" title={document.created_at}>
                    {formatDateTime(document.created_at)}
                  </span>
                }
              />
              <InfoRow
                label="Allowed roles"
                value={
                  <span className="flex flex-wrap gap-1">
                    {document.allowed_roles.map((role) => (
                      <Badge key={role} variant="secondary" className="font-normal">
                        {role}
                      </Badge>
                    ))}
                  </span>
                }
                wide
              />
              <InfoRow
                label="Description"
                value={document.description ?? <span className="text-muted-foreground">No description provided</span>}
                wide
              />
              <InfoRow
                label="Document ID"
                value={
                  <span className="flex items-center gap-1">
                    <code className="min-w-0 break-all font-mono text-[11px]">{document.id}</code>
                    <CopyIdButton value={document.id} label="Copy document ID" />
                  </span>
                }
                wide
              />
            </dl>

            {Object.keys(document.metadata).length > 0 ? (
              <>
                <Separator />
                <div>
                  <h3 className="text-xs font-semibold tracking-tight text-foreground">Metadata</h3>
                  <dl className="mt-2 grid grid-cols-1 gap-x-6 gap-y-2 text-xs sm:grid-cols-2">
                    {Object.entries(document.metadata).map(([key, value]) => (
                      <InfoRow key={key} label={key} value={<span className="break-words">{renderMetadataValue(value)}</span>} />
                    ))}
                  </dl>
                </div>
              </>
            ) : null}
          </Card>

          {status.isError ? (
            <ErrorState
              error={status.error}
              onRetry={() => {
                void status.refetch()
              }}
            />
          ) : status.isLoading ? (
            <DetailSkeletonStatus />
          ) : status.status !== undefined ? (
            <ProcessingPanel status={status.status} />
          ) : null}
        </div>
      ) : null}
    </div>
  )
}

function InfoRow({ label, value, wide = false }: { label: string; value: React.ReactNode; wide?: boolean }) {
  return (
    <div className={wide ? "sm:col-span-2" : undefined}>
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="mt-0.5 font-medium text-foreground">{value}</dd>
    </div>
  )
}

/** Safe JSON display for detail metadata (never objects/arrays). */
function renderMetadataValue(value: unknown): string {
  if (value === null) return "—"
  if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") {
    return String(value)
  }
  return "—"
}

function DetailSkeletonStatus() {
  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex items-center justify-between">
        <Skeleton className="h-4 w-24" />
        <Skeleton className="h-5 w-20" />
      </div>
      <div className="flex gap-8">
        <Skeleton className="h-6 w-16" />
        <Skeleton className="h-6 w-16" />
      </div>
      <Skeleton className="h-2 w-full" />
    </Card>
  )
}

function DetailSkeleton() {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card className="p-5">
        <div className="flex items-center gap-3">
          <Skeleton className="size-8 rounded-md" />
          <Skeleton className="h-5 w-48" />
        </div>
        <div className="mt-6 flex flex-col gap-3">
          {[0, 1, 2, 3].map((row) => (
            <Skeleton key={row} className="h-4 w-full max-w-72" />
          ))}
        </div>
      </Card>
      <Card className="p-5">
        <Skeleton className="h-4 w-24" />
        <div className="mt-6 flex flex-col gap-3">
          <Skeleton className="h-3 w-full" />
          <Skeleton className="h-2 w-3/4" />
        </div>
      </Card>
    </div>
  )
}
