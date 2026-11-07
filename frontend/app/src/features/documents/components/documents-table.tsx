import { Link } from "react-router-dom"

import { Badge } from "@/components/ui/badge"
import { Table, TableBody, TableCaption, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { StatusBadge } from "@/components/shared/status-badge"
import { DocumentTypeIcon } from "@/components/shared/document-type-icon"
import { CopyIdButton } from "@/components/shared/copy-id-button"
import { formatDate } from "@/lib/utils/format"
import type { DocumentSummary } from "@/features/documents/types/document.types"

/**
 * Responsive document table for `lg` and wider viewports. Every cell shows a
 * contract-defined DocumentSummary field; the title links to the detail page
 * and a copy-ID action is available without navigation.
 *
 * On smaller screens the parent renders `DocumentsGrid` instead — tables never
 * scroll horizontally on mobile.
 */
export function DocumentsTable({
  documents,
  caption,
}: {
  documents: DocumentSummary[]
  caption?: string
}) {
  return (
    <Table>
      <TableCaption className="sr-only">{caption}</TableCaption>
      <TableHeader>
        <TableRow>
          <TableHead className="w-12">
            <span className="sr-only">File type</span>
          </TableHead>
          <TableHead className="min-w-56">Title</TableHead>
          <TableHead className="w-28">Status</TableHead>
          <TableHead className="hidden min-w-32 sm:table-cell">Access</TableHead>
          <TableHead className="w-20 text-right">Chunks</TableHead>
          <TableHead className="w-40 text-right">Created</TableHead>
          <TableHead className="w-10 text-right">
            <span className="sr-only">Actions</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {documents.map((document) => (
          <TableRow key={document.id} className="group">
            <TableCell>
              <DocumentTypeIcon sourceType={document.source_type} />
            </TableCell>
            <TableCell>
              <Link
                to={`/documents/${document.id}`}
                className="font-medium text-foreground outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring"
              >
                {document.title}
                <span className="sr-only"> — open document details</span>
              </Link>
            </TableCell>
            <TableCell>
              <StatusBadge status={document.status} />
            </TableCell>
            <TableCell className="hidden sm:table-cell">
              <div className="flex flex-wrap gap-1">
                {document.allowed_roles.map((role) => (
                  <Badge key={role} variant="secondary" className="font-normal">
                    {role}
                  </Badge>
                ))}
              </div>
            </TableCell>
            <TableCell className="text-right tabular-nums">{document.chunk_count}</TableCell>
            <TableCell className="text-right tabular-nums text-xs text-muted-foreground">
              {formatDate(document.created_at)}
            </TableCell>
            <TableCell className="text-right">
              <CopyIdButton
                value={document.id}
                label={`Copy document ID for ${document.title}`}
                className="opacity-60 transition-opacity group-hover:opacity-100 group-focus-visible:opacity-100"
              />
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  )
}
