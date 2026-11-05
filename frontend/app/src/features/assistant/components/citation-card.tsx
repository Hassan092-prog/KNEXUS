import { type Citation } from "@/features/assistant/types/assistant.types"

/**
 * Citation card — presentation-only reference to a source document chunk.
 * Displays document title, page, excerpt, and similarity score. No data
 * fetching; content is passed in by the parent (Z04).
 */
export function CitationCard({ citation }: { citation: Citation }) {
  return (
    <div className="flex items-start gap-3 p-3 rounded-lg border border-border bg-muted/50 text-xs">
      <span className="shrink-0 font-mono text-muted-foreground">
        [{citation.id}]
      </span>
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium text-foreground truncate" title={citation.document_title}>
          {citation.document_title}
        </p>
        <p className="mt-0.5 text-xs text-muted-foreground leading-relaxed">
          {citation.excerpt}
        </p>
        <div className="mt-1 flex items-center gap-1.5 text-[10px] text-muted-foreground/70">
          <span>p. {citation.page ?? "—"}</span>
          <span aria-hidden="true">·</span>
          <span>sim. {citation.similarity_score.toFixed(2)}</span>
        </div>
      </div>
    </div>
  )
}
