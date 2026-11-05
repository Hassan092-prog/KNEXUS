import { cn } from "@/lib/utils"

/**
 * Compact stat card: a prominent value with a label and optional caption.
 * No trend indicators or unsupported analytics — values come from real data only.
 */
export function StatCard({
  value,
  label,
  caption,
  className,
}: {
  value: React.ReactNode
  label: string
  caption?: string
  className?: string
}) {
  return (
    <div className={cn("flex flex-col gap-1", className)}>
      <p className="text-sm font-semibold tabular-nums text-foreground">{value}</p>
      <p className="text-xs text-muted-foreground leading-none">{label}</p>
      {caption ? (
        <p className="text-xs text-muted-foreground/70 leading-none">{caption}</p>
      ) : null}
    </div>
  )
}
