import { cn } from "@/lib/utils"

/**
 * Metric card: prominent value with label, optional icon and caption.
 * Surface, border, and padding are consistent across all instances.
 * Labels use sentence case at a readable size; the numeric value is the
 * strongest visual element on the card.
 */
export function StatCard({
  value,
  label,
  caption,
  icon,
  className,
}: {
  value: React.ReactNode
  label: string
  caption?: string
  icon?: React.ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        "flex h-full flex-col justify-between rounded-lg border border-border bg-card p-5",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-medium text-muted-foreground">
          {label}
        </p>
        {icon ? <span className="text-muted-foreground">{icon}</span> : null}
      </div>
      <p className="mt-3 text-2xl font-semibold tabular-nums text-foreground">
        {value}
      </p>
      {caption ? (
        <p className="mt-2 text-xs text-muted-foreground leading-relaxed">{caption}</p>
      ) : null}
    </div>
  )
}
