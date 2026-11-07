import { useState } from "react"
import { CheckIcon, CopyIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { cn } from "@/lib/utils"

/**
 * Copies a value (typically a document UUID) to the clipboard with visual and
 * screen-reader feedback. Fallback textarea for browsers without the async
 * clipboard API; never used as a progress/processing control.
 */
export function CopyIdButton({
  value,
  label = "Copy to clipboard",
  className,
}: {
  value: string
  label?: string
  className?: string
}) {
  const [copied, setCopied] = useState(false)

  async function copy() {
    try {
      if (navigator.clipboard !== undefined) {
        await navigator.clipboard.writeText(value)
      } else {
        const helper = document.createElement("textarea")
        helper.value = value
        document.body.append(helper)
        helper.select()
        document.execCommand("copy")
        helper.remove()
      }
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1500)
    } catch {
      // Clipboard permission denied — feedback stays silent, data unchanged.
    }
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon-sm"
          onClick={() => {
            void copy()
          }}
          aria-label={label}
          className={cn("text-muted-foreground", className)}
        >
          {copied ? (
            <CheckIcon className="size-3.5 text-status-complete-foreground" aria-hidden="true" />
          ) : (
            <CopyIcon className="size-3.5" aria-hidden="true" />
          )}
        </Button>
      </TooltipTrigger>
      <TooltipContent>{copied ? "Copied" : "Copy ID"}</TooltipContent>
    </Tooltip>
  )
}
