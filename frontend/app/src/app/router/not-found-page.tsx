import { Link } from "react-router-dom"

import { Button } from "@/components/ui/button"
import { EmptyState } from "@/components/shared/empty-state"

/** 404 route — no invented content. */
export function NotFoundPage() {
  return (
    <EmptyState
      title="Page not found"
      description="The requested page does not exist in the KNEXUS application."
      action={
        <Button asChild variant="outline" size="sm">
          <Link to="/">Back to overview</Link>
        </Button>
      }
    />
  )
}
