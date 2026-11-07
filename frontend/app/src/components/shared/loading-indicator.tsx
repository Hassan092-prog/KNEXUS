import { Loader2Icon } from "lucide-react"
import { cn } from "@/lib/utils"

/** Accessible inline loading indicator with an announcement for assistive tech. */
export function LoadingIndicator({
  label = "Loading",
  className,
}: {
  label?: string
  className?: string
}) {
  return (
    <span className={cn("inline-flex items-center gap-2 text-muted-foreground", className)}>
      <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
      <span role="status" aria-live="polite" className="text-sm">
        {label}
      </span>
    </span>
  )
}
