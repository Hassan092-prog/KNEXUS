import { useParams } from "react-router-dom"

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { PageHeader } from "@/components/shared/page-header"

/**
 * Document detail — visual foundation only.
 * Renders metadata and status presentation using verified contract fields.
 * No data fetching, status polling, or document-management interactions
 * (those land in phase Z03). No fabricated values are shown.
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
        description={`Document ${documentId}. Detail and status rendering land in phase Z03.`}
      />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <Card className="col-span-2 lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-base font-semibold">Document metadata</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-muted-foreground">Document ID</p>
                <p className="text-sm font-mono text-foreground truncate" title={documentId}>
                  {documentId}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Source type</p>
                <p className="text-sm font-medium text-foreground">Not loaded</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Allowed roles</p>
                <p className="text-sm font-medium text-foreground">Not loaded</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Chunk count</p>
                <p className="text-sm tabular-nums text-foreground">Not available</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Status</p>
                <p className="text-sm font-medium text-foreground">Not connected</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Created</p>
                <p className="text-sm font-mono text-foreground">Not loaded</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="col-span-2 lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-base font-semibold">Processing status</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-3">
            <div className="flex items-center justify-between">
              <span className="text-sm font-medium text-foreground">Ingestion</span>
              <span className="text-xs font-medium text-muted-foreground">Not connected</span>
            </div>
            <p className="text-xs text-muted-foreground">
              Status polling and failure rendering land in phase Z03.
            </p>
          </CardContent>
        </Card>
      </div>
    </>
  )
}
