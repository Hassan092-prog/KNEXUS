import { PageHeader } from "@/components/shared/page-header"
import { EmptyState } from "@/components/shared/empty-state"
import { QueryInput } from "@/features/assistant/components/query-input"

/**
 * Assistant workspace — visual foundation only.
 */
export function AssistantPage() {
  return (
    <>
      <PageHeader
        title="Assistant"
        description="Ask questions about your organization's documents."
      />

      <div className="flex flex-col gap-4">
        <EmptyState
          title="No conversation yet"
          description="Ask a question about your documents. Answers with inline citations will appear here once the assistant is connected."
        />

        <div>
          <QueryInput />
          <p className="mt-2 text-xs text-muted-foreground">
            The assistant query workflow (submission, streaming, conversation history) is implemented in phase Z04.
          </p>
        </div>
      </div>
    </>
  )
}