import { Link } from "react-router-dom"
import type { DocumentSummary } from "@/features/documents/types/document.types"
import { StatusBadge } from "@/components/shared/status-badge"
import { DocumentTypeIcon } from "@/components/shared/document-type-icon"

/**
 * A single document table row. Uses only verified DocumentSummary contract
 * fields — no invented properties. Presentation only; no interactions beyond
 * the title link to the document detail route.
 */
export function DocumentRow({ document }: { document: DocumentSummary }) {
  return (
    <tr className="hover:bg-muted/50 transition-colors">
      <td className="px-4 py-3">
        <DocumentTypeIcon sourceType={document.source_type} />
      </td>
      <td className="px-4 py-3">
        <Link
          to={`/documents/${document.id}`}
          className="truncate font-medium text-foreground outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring"
        >
          {document.title}
        </Link>
        <p className="mt-0.5 text-xs text-muted-foreground">
          {document.allowed_roles.join(", ")}
        </p>
      </td>
      <td className="px-4 py-3">
        <StatusBadge status={document.status} />
      </td>
      <td className="px-4 py-3 hidden sm:table-cell">
        <span className="tabular-nums text-xs text-muted-foreground">
          {document.chunk_count}
        </span>
      </td>
      <td className="px-4 py-3 text-right tabular-nums text-xs text-muted-foreground">
        {new Date(document.created_at).toLocaleDateString()}
      </td>
    </tr>
  )
}
