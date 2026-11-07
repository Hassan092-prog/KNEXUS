import { PageHeader } from "@/components/shared/page-header"
import { EmptyState } from "@/components/shared/empty-state"

/**
 * Document library — visual foundation only.
 * Renders a clean library surface with a section header and a deliberate
 * disconnected empty state. Data population, upload, search, filtering, and
 * interactive pagination land in phase Z03.
 */
export function DocumentLibraryPage() {
  return (
    <>
      <PageHeader
        title="Documents"
        description="Manage documents available to your organization's knowledge base."
      />
      <section className="rounded-lg border border-border bg-card p-5">
        <div className="flex items-start justify-between gap-3 mb-4">
          <div>
            <h2 className="text-sm font-semibold tracking-tight text-foreground">
              Document library
            </h2>
            <p className="mt-1 text-xs text-muted-foreground">
              Documents and their processing information.
            </p>
          </div>
        </div>
        <EmptyState
          variant="surface"
          title="Document library not connected"
          description="List, upload, search, filtering, and pagination workflows are implemented in phase Z03. This view is a visual foundation only."
        />
      </section>
    </>
  )
}
