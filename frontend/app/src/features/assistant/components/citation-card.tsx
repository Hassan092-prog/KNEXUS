import type { Citation } from "@/features/assistant/types/assistant.types"

/**
 * Citation card — a returned evidence chunk supporting an answer. Displays
 * only contract fields: reference ID (matching the inline `[N]` marker in the
 * answer), document title, chunk index, one-based page (PDFs only; DOCX
 * citations are null), excerpt, and cosine similarity. No invented links: the
 * backend supplies no document-source navigation route in Phase 1.
 */
export function CitationCard({ citation }: { citation: Citation }) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-border bg-muted/40 p-3 text-xs">
      <span aria-label={`Citation ${citation.id}`} className="font-mono text-muted-foreground tabular-nums">
        [{citation.id}]
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs font-medium text-foreground" title={citation.document_title}>
          {citation.document_title}
        </p>
        <p className="mt-1 break-words text-xs text-muted-foreground leading-relaxed">{citation.excerpt}</p>
        <p className="mt-1.5 flex items-center gap-1.5 text-[10px] tabular-nums text-muted-foreground/80">
          <span>
            chunk {citation.chunk_index + 1}
          </span>
          <span aria-hidden="true">·</span>
          {citation.page !== null ? (
            <span>page {citation.page}</span>
          ) : (
            <span>page unavailable</span>
          )}
          <span aria-hidden="true">·</span>
          <span>similarity {citation.similarity_score.toFixed(2)}</span>
        </p>
      </div>
    </div>
  )
}
