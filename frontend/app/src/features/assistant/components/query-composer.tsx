import { useState } from "react"
import { Loader2Icon, SendIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Textarea } from "@/components/ui/textarea"
import { cn } from "@/lib/utils"

const DEFAULT_MAX_LENGTH = 4000

/**
 * Multiline query composer for `POST /query`.
 *
 * - Enter submits; Shift+Enter inserts a newline.
 * - Character budget mirrors the backend contract (1–4000 after trim); the
 *   counter turns destructive with the over-limit range.
 * - Disabled while a submission is in flight; the parent owns transport state.
 */
export function QueryComposer({
  onSubmit,
  pending = false,
  placeholder = "Ask a question about your documents…",
  maxLength = DEFAULT_MAX_LENGTH,
  className,
  ariaLabel = "Question for the knowledge assistant",
}: {
  onSubmit: (question: string) => void
  pending?: boolean
  placeholder?: string
  maxLength?: number
  className?: string
  ariaLabel?: string
}) {
  const [value, setValue] = useState("")
  const trimmed = value.trim()
  const overLimit = trimmed.length > maxLength
  const canSubmit = !pending && !overLimit && trimmed.length > 0

  function trySubmit() {
    if (!canSubmit) return
    onSubmit(trimmed)
    setValue("")
  }

  return (
    <div className={cn("flex flex-col gap-2", className)}>
      <div className="relative">
        <Textarea
          aria-label={ariaLabel}
          value={value}
          maxLength={maxLength + maxLength / 10}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && !event.shiftKey) {
              event.preventDefault()
              trySubmit()
            }
          }}
          placeholder={placeholder}
          rows={3}
          disabled={pending}
          className="min-h-20 resize-none pb-8"
          aria-invalid={overLimit}
        />
        <span
          aria-live="polite"
          className={cn(
            "absolute bottom-2 right-3 text-[11px] tabular-nums",
            overLimit ? "font-medium text-destructive" : "text-muted-foreground/70",
          )}
        >
          {trimmed.length}/{maxLength}
        </span>
      </div>
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] text-muted-foreground/80">
          Enter to ask · Shift+Enter for a new line
        </p>
        <Button
          type="button"
          onClick={trySubmit}
          disabled={!canSubmit}
          aria-label="Submit question"
          size="sm"
        >
          {pending ? (
            <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
          ) : (
            <SendIcon className="size-4" aria-hidden="true" />
          )}
          Ask
        </Button>
      </div>
      {overLimit ? (
        <p role="alert" className="text-xs font-medium text-destructive">
          The question exceeds the maximum of {maxLength} characters after trimming.
        </p>
      ) : null}
    </div>
  )
}
