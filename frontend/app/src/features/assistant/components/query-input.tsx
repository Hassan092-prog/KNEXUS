import { SendIcon } from "lucide-react"
import { cn } from "@/lib/utils"

import { Button } from "@/components/ui/button"

/**
 * Query input — presentation-only input area.
 * Renders a text input and submit button. Not connected to POST /query;
 * wiring lands in Z04. The submit button is disabled to indicate the
 * workflow is not yet active.
 */
export function QueryInput({
  onSubmit,
  placeholder = "Ask a question about your documents…",
  disabled = true,
  className,
}: {
  onSubmit?: () => void
  placeholder?: string
  disabled?: boolean
  className?: string
}) {
  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-lg border border-border bg-card p-3",
        className,
      )}
    >
      <input
        type="text"
        placeholder={placeholder}
        disabled={disabled}
        className={cn(
          "flex-1 min-w-0 bg-transparent text-sm text-foreground placeholder:text-muted-foreground/50 outline-none disabled:cursor-not-allowed disabled:text-muted-foreground/40",
        )}
      />
      <Button
        onClick={onSubmit}
        disabled={disabled}
        className="shrink-0"
        aria-label="Submit query"
      >
        <SendIcon className="size-4" aria-hidden="true" />
      </Button>
    </div>
  )
}
