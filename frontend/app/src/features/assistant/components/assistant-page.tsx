import { BotIcon } from "lucide-react"

import { PageHeader } from "@/components/shared/page-header"
import { QueryInput } from "@/features/assistant/components/query-input"

/**
 * Assistant workspace — visual foundation only.
 * Single-column conversation workspace with a clear disconnected state and
 * one composer. The query workflow is not connected; wiring lands in Z04.
 * No fabricated responses, citations, or submission behavior.
 */
export function AssistantPage() {
  return (
    <>
      <PageHeader
        title="Assistant"
        description="Ask questions about your organization's documents."
      />

      <section className="flex flex-col gap-6">
        {/* Conversation workspace — empty / disconnected state */}
        <div className="flex-1 flex flex-col items-center justify-center gap-4 rounded-lg border border-border bg-card p-8 sm:p-12 text-center">
          <BotIcon className="size-8 text-muted-foreground/40" aria-hidden="true" />
          <div>
            <h2 className="text-sm font-semibold tracking-tight text-foreground">
              Your knowledge assistant
            </h2>
            <p className="mt-1 text-sm text-muted-foreground leading-relaxed">
              Ask questions using information from your documents.
            </p>
          </div>
          <p className="text-xs text-muted-foreground">
            The assistant query workflow is not connected yet.
          </p>
        </div>

        {/* Query composer */}
        <div className="rounded-lg border border-border bg-card p-5">
          <QueryInput />
          <p className="mt-2 text-xs text-muted-foreground leading-relaxed">
            The assistant query workflow (submission, streaming, conversation
            history) is implemented in phase Z04.
          </p>
        </div>
      </section>
    </>
  )
}
