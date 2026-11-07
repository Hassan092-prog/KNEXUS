import type { LucideIcon } from "lucide-react"
import { FolderOpenIcon } from "lucide-react"
import { cn } from "@/lib/utils"

/**
 * Reusable empty state for lists/pages with no backing data.
 *
 * Variants:
 * - `default` — full-page centered state with card surface and dashed border.
 * - `surface` — compact state that belongs inside a library/table surface
 *   (no card background, no dashed border).
 * - `disconnected` — workflow-not-connected state with a modest icon,
 *   clear heading, and short explanation; no borders or card surface.
 */
export type EmptyStateVariant = "default" | "surface" | "disconnected"

export function EmptyState({
  title,
  description,
  icon: Icon = FolderOpenIcon,
  action,
  className,
  variant = "default",
}: {
  title: string
  description?: string
  icon?: LucideIcon
  action?: React.ReactNode
  className?: string
  variant?: EmptyStateVariant
}) {
  const base = "flex flex-col items-center justify-center gap-3 text-center"

  const surfaceStyles: Record<EmptyStateVariant, string> = {
    default:
      "rounded-xl border border-dashed border-border bg-card p-8 sm:p-10",
    surface: "p-6 sm:p-8",
    disconnected: "p-6 sm:p-8 gap-4",
  }

  const iconStyles: Record<EmptyStateVariant, string> = {
    default: "size-7 text-muted-foreground/60",
    surface: "size-5 text-muted-foreground/50",
    disconnected: "size-6 text-muted-foreground/50",
  }

  return (
    <div className={cn(base, surfaceStyles[variant], className)}>
      <Icon className={iconStyles[variant]} aria-hidden="true" />
      <p className="text-sm font-medium text-foreground">{title}</p>
      {description ? (
        <p className="max-w-sm text-sm text-muted-foreground leading-relaxed">
          {description}
        </p>
      ) : null}
      {action ? <div className="mt-4">{action}</div> : null}
    </div>
  )
}
