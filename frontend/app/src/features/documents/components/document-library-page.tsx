import { PageHeader } from "@/components/shared/page-header"
import { EmptyState } from "@/components/shared/empty-state"
import { DataTable } from "@/features/documents/components/data-table"

/**
 * Document library — visual foundation only.
 * Renders the table column-header convention and an empty state.
 * Data population, upload, search, filtering, and interactive pagination
 * land in phase Z03.
 */
export function DocumentLibraryPage() {
  return (
    <>
      <PageHeader
        title="Documents"
        description="Manage documents available to your organization's knowledge base."
      />
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <DataTable headers={["Type", "Title", "Roles", "Status", "Chunks", "Created"]} />
        <div className="p-6">
          <EmptyState
            title="Document library not connected"
            description="List, upload, search, filtering, and pagination workflows are implemented in phase Z03. This view is a visual foundation only."
          />
        </div>
      </div>
    </>
  )
}
