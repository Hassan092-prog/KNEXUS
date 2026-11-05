import { PageHeader } from "@/components/shared/page-header"
import { EmptyState } from "@/components/shared/empty-state"
import { QueryInput } from "@/features/assistant/components/query-input"

/**
 * Assistant workspace — visual foundation only.
 * Establishes the conversation layout and query composer. Presentation-only:
 * no POST /query wiring, no streaming, no conversation persistence (those
 * land in phase Z04). No fabricated conversations or sample responses.
 */
export function AssistantPage() {
  return (
    <>
      <PageHeader
        title="Assistant"
        description="Ask questions about your documents. Answers with inline citations will appear here."
      />

      <div className="flex flex-col gap-4">
        {/* Conversation area — empty state until Z04 wiring exists */}
        <div className="flex-1 flex flex-col">
          <EmptyState
            title="No conversation yet"
            description="Ask a question about your documents. Answers with inline [N] citations linked to source chunks will appear here."
            action={
              <div className="text-left w-full">
                <QueryInput />
              </div>
            }
          />
        </div>

        {/* Query composer — single instance at bottom, presentation only */}
        <div className="mt-4">
          <QueryInput />
          <p className="mt-2 text-xs text-muted-foreground">
            The assistant workflow (query submission, streaming, conversation
            history) is implemented in phase Z04.
          </p>
        </div>
      </div>
    </>
  )
}
