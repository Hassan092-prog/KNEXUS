import { useState } from "react"
import type { Citation } from "@/features/assistant/types/assistant.types"

/**
 * Maximum number of excerpt characters shown before the "Show more" toggle.
 * Keeps a card to a scannable preview instead of a wall of chunk text.
 */
const PREVIEW_MAX_CHARS = 300

/**
 * Citation card — a returned evidence chunk supporting an answer. Displays
 * only contract fields: reference ID (matching the inline `[N]` marker in the
 * answer), document title, chunk index, one-based page (PDFs only; DOCX
 * citations are null and the page is simply omitted), excerpt preview, and
 * cosine similarity. No invented links: the backend supplies no
 * document-source navigation route in Phase 1.
 */
export function CitationCard({ citation }: { citation: Citation }) {
  const [expanded, setExpanded] = useState(false)

  const isTruncatable = citation.excerpt.length > PREVIEW_MAX_CHARS
  const visibleExcerpt =
    expanded || !isTruncatable ? citation.excerpt : truncateText(citation.excerpt, PREVIEW_MAX_CHARS)

  // The page only exists for paginated sources; a null page is omitted
  // instead of being rendered as a placeholder.
  const meta = [
    `chunk ${citation.chunk_index + 1}`,
    ...(citation.page !== null ? [`page ${citation.page}`] : []),
    `similarity ${citation.similarity_score.toFixed(2)}`,
  ]

  return (
    <div className="flex items-start gap-3 rounded-lg border border-border bg-muted/40 p-3 text-xs">
      <span aria-label={`Citation ${citation.id}`} className="font-mono text-muted-foreground tabular-nums">
        [{citation.id}]
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate text-xs font-medium text-foreground" title={citation.document_title}>
          {citation.document_title}
        </p>
        <p className="mt-1 break-words text-xs text-muted-foreground leading-relaxed">{visibleExcerpt}</p>
        {isTruncatable ? (
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            className="mt-1 cursor-pointer text-[10px] text-primary underline underline-offset-2 hover:text-foreground"
          >
            {expanded ? "Show less" : "Show more"}
          </button>
        ) : null}
        <p className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[10px] tabular-nums text-muted-foreground/80">
          {meta.map((item, index) => (
            <span key={item} className="flex items-center gap-1.5">
              {index > 0 ? (
                <span aria-hidden="true">·</span>
              ) : null}
              {item}
            </span>
          ))}
        </p>
      </div>
    </div>
  )
}

function truncateText(text: string, maxChars: number): string {
  if (text.length <= maxChars) return text
  return text.substring(0, maxChars).trimEnd() + "..."
}
