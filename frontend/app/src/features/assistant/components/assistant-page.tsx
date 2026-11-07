import { useMemo, useState } from "react"
import { BotIcon, Loader2Icon, SparklesIcon } from "lucide-react"

import { Card } from "@/components/ui/card"
import { PageHeader } from "@/components/shared/page-header"
import { ErrorState } from "@/components/shared/error-state"
import { QueryComposer } from "@/features/assistant/components/query-composer"
import { MessageBubble } from "@/features/assistant/components/message-bubble"
import { CitationCard } from "@/features/assistant/components/citation-card"
import { AbstentionCard } from "@/features/assistant/components/abstention-card"
import { getAssistantApi } from "@/lib/api"
import { ApiError, toApiError } from "@/lib/api/error"
import type { QueryResponse } from "@/features/assistant/types/assistant.types"

/**
 * Assistant workspace for `POST /api/v1/query`.
 *
 * Phase 1 is one-shot and non-streaming: no conversation history, persistent
 * sessions, or streaming exist in the backend, so messages are transient
 * client state and exactly one request is in flight at a time. Answer,
 * abstention, and error are distinct outcomes — an abstention is a valid 200.
 */
export function AssistantPage() {
  return (
    <>
      <PageHeader
        title="Assistant"
        description="Ask questions about the organization's documents. Answers always show their sources."
      />
      <AssistantThread />
    </>
  )
}

type QuestionStatus = "pending" | "answered" | "abstained" | "failed"

interface QuestionEntry {
  id: string
  question: string
  status: QuestionStatus
  response?: QueryResponse
  /** Normalized failure for provider/network/validation outcomes. */
  error?: ApiError
}

function AssistantThread() {
  const [entries, setEntries] = useState<QuestionEntry[]>([])
  const [pending, setPending] = useState(false)

  const hasConversation = entries.length > 0

  function submitQuestion(question: string) {
    if (pending) return
    const entryId = createEntryId()
    setEntries((current) => [...current, { id: entryId, question, status: "pending" }])
    setPending(true)

    void getAssistantApi()
      .submitQuery({ question, top_k: 5, stream: false })
      .then((response) => {
        setEntries((current) =>
          current.map((entry) =>
            entry.id === entryId
              ? { ...entry, status: response.abstained ? "abstained" : "answered", response }
              : entry,
          ),
        )
      })
      .catch((error: unknown) => {
        const normalized = new ApiError(toApiError(error))
        setEntries((current) =>
          current.map((entry) =>
            entry.id === entryId
              ? { ...entry, status: "failed", error: normalized }
              : entry,
          ),
        )
      })
      .finally(() => {
        setPending(false)
      })
  }

  const reversed = useMemo(() => [...entries].reverse(), [entries])

  return (
    <section aria-label="Assistant conversation" className="flex flex-col gap-6">
      <div className="flex min-h-40 flex-col gap-4" aria-live="polite">
        {hasConversation ? null : (
          <div className="flex flex-1 flex-col items-center justify-center gap-3 rounded-lg border border-border bg-card p-8 text-center sm:p-12">
            <BotIcon className="size-8 text-muted-foreground/40" aria-hidden="true" />
            <div>
              <h2 className="text-sm font-semibold tracking-tight text-foreground">
                Your knowledge assistant
              </h2>
              <p className="mt-1 max-w-md text-sm text-muted-foreground leading-relaxed">
                Ask a question and KNEXUS answers with citations drawn from
                documents the assistant is permitted to read. When the knowledge
                base lacks sufficient evidence, it says so instead of guessing.
              </p>
            </div>
          </div>
        )}

        {reversed.map((entry) => (
          <AssistantEntryCard key={entry.id} entry={entry} />
        ))}
      </div>

      <Card className="p-4 sm:p-5">
        <QueryComposer onSubmit={submitQuestion} pending={pending} />
        <p className="mt-3 text-[11px] text-muted-foreground leading-relaxed">
          One question at a time — Phase 1 answers are standalone (no
          conversation history). Retrieval covers the assistant&apos;s
          accessible documents only.
        </p>
      </Card>
    </section>
  )
}

function AssistantEntryCard({ entry }: { entry: QuestionEntry }) {
  return (
    <div className="flex flex-col gap-2">
      <MessageBubble variant="question" content={entry.question} />

      {entry.status === "pending" ? (
        <div
          role="status"
          className="flex items-center gap-2 rounded-xl border border-border bg-card p-4 text-sm text-muted-foreground"
        >
          <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
          Retrieving evidence and generating an answer…
        </div>
      ) : null}

      {entry.status === "answered" && entry.response ? (
        <MessageBubble variant="answer" content={entry.response.answer ?? ""}>
          <div className="flex flex-col gap-2">
            <p className="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              Citations ({entry.response.citations.length})
            </p>
            {entry.response.citations.map((citation) => (
              <CitationCard key={citation.id} citation={citation} />
            ))}
            <ResponseMeta
              model={entry.response.meta.model}
              retrievalTimeMs={entry.response.meta.retrieval_time_ms}
              generationTimeMs={entry.response.meta.generation_time_ms}
            />
          </div>
        </MessageBubble>
      ) : null}

      {entry.status === "abstained" && entry.response ? (
        <AbstentionCard reason={entry.response.abstention_reason} />
      ) : null}

      {entry.status === "failed" && entry.error ? (
        <ErrorState error={entry.error} />
      ) : null}
    </div>
  )
}

/** Quiet meta row: model + timings, both measured server-side. */
function ResponseMeta({
  model,
  retrievalTimeMs,
  generationTimeMs,
}: {
  model: string
  retrievalTimeMs: number
  generationTimeMs: number
}) {
  return (
    <p className="flex flex-wrap items-center gap-2 pt-1 text-[10px] text-muted-foreground/70">
      <SparklesIcon className="size-3" aria-hidden="true" />
      <span>model {model}</span>
      <span aria-hidden="true">·</span>
      <span>retrieval {Math.round(retrievalTimeMs)} ms</span>
      <span aria-hidden="true">·</span>
      <span>generation {Math.round(generationTimeMs)} ms</span>
    </p>
  )
}

/** Stable per-entry identifier for the message list. */
function createEntryId(): string {
  try {
    return crypto.randomUUID()
  } catch {
    return `entry-${Date.now()}-${Math.floor(Math.random() * 1e6)}`
  }
}
