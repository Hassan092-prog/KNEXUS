import { MessageCircleIcon } from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * Message bubble — presentation-only message container.
 * Renders answer text with inline [N] citation markers and optional citation
 * cards. No data fetching; content is passed in by the parent (Z04).
 */
export function MessageBubble({
  content,
  citations,
  className,
}: {
  content: string
  citations?: React.ReactNode[]
  className?: string
}) {
  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-xl border border-border bg-card p-4 text-sm text-foreground leading-relaxed",
        className,
      )}
    >
      <div className="flex items-start gap-2">
        <MessageCircleIcon className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
        <div className="prose prose-sm text-sm max-w-none">{content}</div>
      </div>
      {citations ? (
        <div className="mt-2 flex flex-col gap-2">{citations}</div>
      ) : null}
    </div>
  )
}
