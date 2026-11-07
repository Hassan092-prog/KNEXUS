import { useCallback, useId, useRef, useState } from "react"
import { FileUpIcon, FileX2Icon } from "lucide-react"
import { cn } from "@/lib/utils"

import { formatByteSize } from "@/lib/utils/format"
import { ACCEPT_ATTRIBUTE, MAX_UPLOAD_BYTES, type UploadFileError } from "@/features/documents/upload-constraints"

/**
 * Single-file upload dropzone. Handles drag & drop plus keyboard/pointer
 * file selection; validation feedback is rendered by the parent dialog so
 * error display ownership stays with the form.
 */
export function UploadDropzone({
  file,
  error,
  onFileSelected,
  disabled,
}: {
  file: File | null
  error: UploadFileError | null
  onFileSelected: (file: File | null) => void
  disabled?: boolean
}) {
  const inputId = useId()
  const inputRef = useRef<HTMLInputElement>(null)
  const [isDragging, setDragging] = useState(false)

  const acceptSelection = useCallback(
    (list: FileList | null) => {
      const selected = list?.[0] ?? null
      // It is a one-file upload; anything beyond the first is ignored the same
      // way the backend rejects extra `file` parts.
      onFileSelected(selected)
    },
    [onFileSelected],
  )

  return (
    <div
      className={cn(
        "rounded-lg border border-dashed border-border bg-muted/30 transition-colors",
        isDragging && "border-ring bg-accent/40",
        disabled && "pointer-events-none opacity-60",
      )}
    >
      <label
        htmlFor={inputId}
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(event) => {
          event.preventDefault()
          setDragging(false)
          acceptSelection(event.dataTransfer.files)
        }}
        className="flex cursor-pointer flex-col items-center gap-2 px-4 py-6 text-center outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-describedby={error ? `${inputId}-error` : undefined}
        onKeyDown={(event) => {
          if (event.key === " " || event.key === "Enter" || event.key === "Space") {
            event.preventDefault()
            inputRef.current?.click()
          }
        }}
        tabIndex={disabled ? -1 : 0}
        role="button"
        aria-label="Upload PDF or DOCX file"
      >
        {error ? (
          <FileX2Icon className="size-5 text-destructive" aria-hidden="true" />
        ) : (
          <FileUpIcon className="size-5 text-muted-foreground" aria-hidden="true" />
        )}
        <p className="text-sm font-medium text-foreground">
          {file ? file.name : "Drop a PDF or DOCX here, or click to browse"}
        </p>
        <p className="text-xs text-muted-foreground">
          {file
            ? formatByteSize(file.size)
            : `PDF and DOCX · up to ${formatByteSize(MAX_UPLOAD_BYTES)}`}
        </p>
      </label>
      <input
        ref={inputRef}
        id={inputId}
        type="file"
        accept={ACCEPT_ATTRIBUTE}
        className="sr-only"
        disabled={disabled}
        onChange={(event) => {
          acceptSelection(event.target.files)
          event.target.value = ""
        }}
      />
      <span id={`${inputId}-error`} className="sr-only" role="alert" aria-live="polite">
        {error?.detail}
      </span>
    </div>
  )
}
