import { cn } from "@/lib/utils"
import type { DocumentState } from "@/features/documents/types/document.types"

/**
 * Maps the backend's document lifecycle state to a consistent visual chip.
 * Status colors come from centralized semantic tokens (--status-*-background /
 * --status-*-foreground) so a single token change updates every instance.
 * Terminal states (`complete`, `failed`) are visually distinct without
 * implying backend semantics beyond the state itself.
 */

const statusStyles: Record<DocumentState, { bg: string; fg: string; label: string }> = {
  queued: {
    bg: "bg-status-queued-background text-status-queued-foreground border-status-queued-background/30",
    fg: "",
    label: "Queued",
  },
  processing: {
    bg: "bg-status-processing-background text-status-processing-foreground border-status-processing-background/30",
    fg: "",
    label: "Processing",
  },
  complete: {
    bg: "bg-status-complete-background text-status-complete-foreground border-status-complete-background/20",
    fg: "",
    label: "Complete",
  },
  failed: {
    bg: "bg-status-failed-background text-status-failed-foreground border-status-failed-background/30",
    fg: "",
    label: "Failed",
  },
}

export function StatusBadge({
  status,
  className,
}: {
  status: DocumentState
  className?: string
}) {
  const style = statusStyles[status]
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap",
        style.bg,
        className,
      )}
    >
      <span
        aria-hidden="true"
        className={cn(
          "size-1.5 rounded-full",
          status === "processing" ? "bg-current animate-pulse" : "bg-current/60",
        )}
      />
      {style.label}
    </span>
  )
}
