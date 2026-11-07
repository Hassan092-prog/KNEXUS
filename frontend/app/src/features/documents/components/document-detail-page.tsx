import { useParams } from "react-router-dom"

import { PageHeader } from "@/components/shared/page-header"

/**
 * Document detail — visual foundation only.
 * Presents the document identifier and groups unavailable metadata into clear
 * sections with honest messaging. No data fetching, no fabricated values,
 * no invented progress bars. Detail rendering lands in phase Z03.
 */
export function DocumentDetailPage() {
  const { documentId } = useParams<{ documentId: string }>()
  if (!documentId) {
    throw new Error("Document detail route requires a documentId param.")
  }

  return (
    <>
      <PageHeader
        title="Document details"
        description={`Information about document ${documentId} and its processing state.`}
      />
      <section className="rounded-lg border border-border bg-card p-5">
        <div className="mb-6">
          <h2 className="text-sm font-semibold tracking-tight text-foreground">
            Document identifier
          </h2>
          <p className="mt-1 text-xs text-muted-foreground">
            The document ID is used to reference this document across KNEXUS.
          </p>
          <div className="mt-2 font-mono text-sm text-foreground break-all">
            {documentId}
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <h2 className="text-sm font-semibold tracking-tight text-foreground mb-3">
              Document information
            </h2>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Source type, access roles, chunk count, and creation date will
              appear here once the document-detail workflow is connected.
            </p>
          </div>

          <div>
            <h2 className="text-sm font-semibold tracking-tight text-foreground mb-3">
              Processing information
            </h2>
            <p className="text-xs text-muted-foreground leading-relaxed">
              Processing status and chunk details will be available in Z03.
            </p>
          </div>
        </div>
      </section>
    </>
  )
}
