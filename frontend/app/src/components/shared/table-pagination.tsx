import { ChevronLeftIcon, ChevronRightIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"

/**
 * Reusable pagination footer for paged tables/cards. Purely presentational:
 * receives page bounds and a change callback, debouncing and data ownership
 * stay with the parent (business logic stays out of shared components).
 */
export function TablePagination({
  page,
  pageCount,
  onPageChange,
  className,
}: {
  /** 1-based current page. */
  page: number
  pageCount: number
  onPageChange: (page: number) => void
  className?: string
}) {
  return (
    <nav
      aria-label="Pagination"
      className={cn("flex items-center justify-between gap-3 px-1 py-3 text-xs text-muted-foreground", className)}
    >
      <div className="min-w-0">
        Page {page} of {pageCount}
      </div>
      <div className="flex shrink-0 items-center gap-1.5">
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            onPageChange(page - 1)
          }}
          disabled={page <= 1}
        >
          <ChevronLeftIcon className="size-3.5" aria-hidden="true" />
          Prev
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={() => {
            onPageChange(page + 1)
          }}
          disabled={page >= pageCount}
        >
          Next
          <ChevronRightIcon className="size-3.5" aria-hidden="true" />
        </Button>
      </div>
    </nav>
  )
}
