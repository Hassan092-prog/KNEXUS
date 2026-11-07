import { Link } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Card } from "@/components/ui/card"
import { StatusBadge } from "@/components/shared/status-badge"
import { DocumentTypeIcon } from "@/components/shared/document-type-icon"
import { formatDate } from "@/lib/utils/format"
import type { DocumentSummary } from "@/features/documents/types/document.types"

/**
 * Mobile/tablet document card — the responsive counterpart of the table row.
 * All summary fields come from the contract; the title links to the detail
 * page.
 */
export function DocumentCard({ document }: { document: DocumentSummary }) {
  return (
    <Card className="flex gap-3 p-4">
      <DocumentTypeIcon sourceType={document.source_type} className="mt-0.5 size-8" />
      <div className="min-w-0 flex-1">
        <Link
          to={`/documents/${document.id}`}
          className="block font-medium text-foreground outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring"
        >
          {document.title}
          <span className="sr-only"> — open document details</span>
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <StatusBadge status={document.status} />
          <span className="text-xs tabular-nums text-muted-foreground">{document.chunk_count} chunks</span>
          <span className="text-xs tabular-nums text-muted-foreground">{formatDate(document.created_at)}</span>
        </div>
        <div className="mt-2 flex flex-wrap gap-1">
          {document.allowed_roles.map((role) => (
            <Badge key={role} variant="secondary" className="font-normal text-[11px]">
              {role}
            </Badge>
          ))}
        </div>
      </div>
    </Card>
  )
}
