import { CircleHelpIcon } from "lucide-react"

import { Card } from "@/components/ui/card"
import { cn } from "@/lib/utils"

/**
 * Abstention card for a valid 200-with-abstention response: the knowledge
 * base did not supply sufficient evidence. Never an error state.
 */
export function AbstentionCard({ reason, className }: { reason: string | null; className?: string }) {
  return (
    <Card className={cn("flex items-start gap-3 bg-muted/40 p-4", className)}>
      <CircleHelpIcon className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
      <div className="min-w-0">
        <p className="text-sm font-medium text-foreground">No confident answer available</p>
        <p className="mt-1 text-sm text-muted-foreground leading-relaxed">
          The knowledge base did not contain sufficiently relevant evidence for this question.
          {reason ? <span className="block text-xs">Backend reason: {reason}</span> : null}
        </p>
      </div>
      
    </Card>
  )
}
