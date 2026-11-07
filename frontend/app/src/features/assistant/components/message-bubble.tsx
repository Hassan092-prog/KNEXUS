import { BotIcon, UserIcon } from "lucide-react"

import { cn } from "@/lib/utils"

/**
 * Message container for an assistant exchange. Two variants:
 * - `question` — the user's submitted question (muted surface).
 * - `answer` — the assistant's response. Inline `[N]` citation markers are
 *   rendered as small reference chips (they echo the returned citation IDs;
 *   the backend supplies no document links, so they are not links).
 * Citations/menus are passed in as children by the page.
 */
export function MessageBubble({
  variant,
  content,
  children,
  className,
}: {
  variant: "question" | "answer"
  content: string
  children?: React.ReactNode
  className?: string
}) {
  const isQuestion = variant === "question"

  return (
    <div
      className={cn(
        "flex flex-col gap-3 rounded-xl border border-border bg-card p-4 text-sm leading-relaxed text-foreground",
        isQuestion && "bg-muted/50",
        className,
      )}
    >
      <div className="flex items-start gap-2.5">
        <span
          aria-hidden="true"
          className={cn(
            "mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-md",
            isQuestion ? "bg-muted text-muted-foreground" : "bg-primary text-primary-foreground",
          )}
        >
          {isQuestion ? <UserIcon className="size-3.5" /> : <BotIcon className="size-3.5" />}
        </span>
        <div className="min-w-0 flex-1">
          <p role="heading" aria-level={4} className="sr-only">
            {isQuestion ? "Your question" : "Assistant answer"}
          </p>
          <p className="break-words whitespace-pre-wrap">
            {isQuestion ? content : renderAnswerMarkers(content)}
          </p>
        </div>
      </div>
      {children !== undefined && children !== null ? <div className="min-w-0">{children}</div> : null}
    </div>
  )
}

/** Renders answer text, styling `[N]` citation markers as reference chips. */
function renderAnswerMarkers(answer: string): React.ReactNode[] {
  return answer.split(/(\[\d+\])/g).map((piece, index) => {
    if (/^\[\d+\]$/.test(piece)) {
      return (
        <span
          key={`${piece}-${index}`}
          className="mx-0.5 inline-flex items-center rounded-sm border border-border bg-muted px-1 align-super text-[10px] font-medium tabular-nums text-foreground"
          title="Citation reference"
        >
          {piece}
        </span>
      )
    }
    return <span key={`text-${index}`}>{piece}</span>
  })
}
