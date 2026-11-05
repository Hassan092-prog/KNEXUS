import { FileTextIcon, FileIcon } from "lucide-react"
import { cn } from "@/lib/utils"

export type DocumentSourceType = "pdf" | "docx"

/**
 * Maps a document's source type to a consistent icon. Keeps feature-specific
 * icon logic out of shared table/layout components.
 */
export function DocumentTypeIcon({
  sourceType,
  className,
}: {
  sourceType?: DocumentSourceType
  className?: string
}) {
  const Icon = sourceType === "docx" ? FileTextIcon : FileIcon

  return (
    <span
      className={cn("flex shrink-0 items-center justify-center rounded-md bg-muted p-1.5 text-muted-foreground", className)}
      aria-hidden="true"
    >
      <Icon className="size-3.5" />
    </span>
  )
}
