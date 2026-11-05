import type { LucideIcon } from "lucide-react"
import { FolderOpenIcon } from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * Reusable empty state for lists/pages with no backing data.
 * Consistent icon sizing and padding across the application.
 */
export function EmptyState({
  title,
  description,
  icon: Icon = FolderOpenIcon,
  action,
  className,
}: {
  title: string
  description?: string
  icon?: LucideIcon
  action?: React.ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-3 rounded-xl border border-dashed border-border bg-card p-8 text-center",
        className,
      )}
    >
      <Icon className="size-6 text-muted-foreground/60" aria-hidden="true" />
      <p className="text-sm font-medium text-foreground">{title}</p>
      {description ? (
        <p className="max-w-sm text-sm text-muted-foreground leading-relaxed">{description}</p>
      ) : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  )
}
