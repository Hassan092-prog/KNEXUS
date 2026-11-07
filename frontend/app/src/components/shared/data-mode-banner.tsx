import { FlaskConicalIcon } from "lucide-react"

import { getDataMode } from "@/lib/api"

/**
 * Discloses mock/demo data mode once, above routed content. Rendered only in
 * mock mode so live sessions keep a clean workspace; the sidebar footer also
 * reports the mode persistently.
 */
export function DataModeBanner() {
  if (getDataMode() !== "mock") {
    return null
  }

  return (
    <div
      role="status"
      className="mb-4 flex items-center gap-2 rounded-lg border border-status-processing-background/40 bg-status-processing-background/15 px-3 py-2 text-xs text-muted-foreground"
    >
      <FlaskConicalIcon className="size-3.5 shrink-0" aria-hidden="true" />
      <span className="font-medium text-foreground">Demo mode</span>
      <span className="min-w-0">
        Responses are served from local contract fixtures; no backend requests are made.
      </span>
    </div>
  )
}
