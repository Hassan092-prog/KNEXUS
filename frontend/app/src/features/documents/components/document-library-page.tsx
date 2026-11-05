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
        title="Document library"
        description="Browse and manage documents in your knowledge base. List, upload, and status workflows land in phase Z03."
      />
      <DataTable headers={["Type", "Title", "Roles", "Status", "Chunks", "Created"]} />
      <div className="mt-6">
        <EmptyState
          title="No documents yet"
          description="Documents uploaded through the backend will appear here once visible to the server-side demo actor."
        />
      </div>
    </>
  )
}
