import { AlertTriangleIcon } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Card } from "@/components/ui/card"
import { Progress } from "@/components/ui/progress"
import { StatusBadge } from "@/components/shared/status-badge"
import type { DocumentStatusResponse } from "@/features/documents/types/document.types"

/**
 * Processing-state panel driven only by `GET /documents/{id}/status`.
 * Progress is rendered exclusively when the backend provides
 * `progress_percent`; totals are shown as "—/—" when unknown (queued), and
 * failure details use the backend's safe code + message pair verbatim.
 */
export function ProcessingPanel({ status }: { status: DocumentStatusResponse }) {
  const showProgress = status.progress_percent !== null

  return (
    <Card className="flex flex-col gap-4 p-5">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold tracking-tight text-foreground">Processing</h2>
        <StatusBadge status={status.status} />
      </div>

      <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-xs">
        <div>
          <dt className="text-muted-foreground">Chunks processed</dt>
          <dd className="mt-0.5 font-medium tabular-nums text-foreground">{status.chunks_processed}</dd>
        </div>
        <div>
          <dt className="text-muted-foreground">Total chunks</dt>
          <dd className="mt-0.5 font-medium tabular-nums text-foreground">{status.total_chunks ?? "—"}</dd>
        </div>
      </dl>

      {showProgress ? (
        <div>
          <Progress
            value={status.progress_percent ?? 0}
            aria-label={`Processing progress: ${status.progress_percent}%`}
          />
          <p className="mt-1 text-xs text-muted-foreground">{status.progress_percent}% of chunks processed</p>
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          {status.status === "queued"
            ? "Queued — chunk totals are not known until processing begins."
            : status.status === "failed"
              ? "Processing stopped with an error. Details are shown below."
              : "Chunk totals are not yet known."}
        </p>
      )}

      {status.status === "failed" && status.failure_code !== null ? (
        <Alert variant="destructive">
          <AlertTriangleIcon aria-hidden="true" />
          <AlertTitle>Processing failed ({status.failure_code})</AlertTitle>
          <AlertDescription className="break-words">{status.failure_message}</AlertDescription>
        </Alert>
      ) : null}

      {status.status === "failed" ? (
        <p className="text-xs text-muted-foreground">
          Status comes from the backend ingestion record — retries are not supported in Phase 1.
        </p>
      ) : null}
    </Card>
  )
}

