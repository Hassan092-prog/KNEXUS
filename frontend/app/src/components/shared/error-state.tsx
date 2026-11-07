import { RotateCcwIcon } from "lucide-react"

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { Button } from "@/components/ui/button"
import { toApiError, type NormalizedApiError } from "@/lib/api/error"

/**
 * Reusable failure state. Renders the backend's safe detail message (never
 * exception text) plus its canonical error code; offers a retry instead of
 * pretending to be mock data. `error` comes from TanStack Query hooks
 * (`query.error`, typed unknown here) and is normalized in one place.
 */
export function ErrorState({
  error,
  fallbackDetail = "An unexpected error occurred.",
  onRetry,
  className,
}: {
  error: unknown
  fallbackDetail?: string
  onRetry?: () => void
  className?: string
}) {
  const normalized: NormalizedApiError = toApiError(error)

  return (
    <Alert variant="destructive" className={className}>
      <AlertTitle>
        {normalized.code ? `${normalized.code}` : "Request failed"}
      </AlertTitle>
      <AlertDescription className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <span className="min-w-0 break-words">
          {normalized.detail || fallbackDetail}
          {normalized.requestId ? (
            <span className="mt-1 block font-mono text-xs opacity-70">
              Request ID: {normalized.requestId}
            </span>
          ) : null}
        </span>
        {onRetry ? (
          <Button
            variant="outline"
            size="sm"
            onClick={onRetry}
            className="shrink-0 self-start sm:self-auto"
          >
            <RotateCcwIcon className="size-4" aria-hidden="true" />
            Retry
          </Button>
        ) : null}
      </AlertDescription>
    </Alert>
  )
}
