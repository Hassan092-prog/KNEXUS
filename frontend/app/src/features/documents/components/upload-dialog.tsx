import { useEffect, useId, useMemo, useState } from "react"
import { useNavigate } from "react-router-dom"
import { Loader2Icon, UploadIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { Textarea } from "@/components/ui/textarea"
import { Alert, AlertDescription } from "@/components/ui/alert"
import { DOCUMENT_ROLES, uploadMetadataSchema } from "@/lib/api/contracts"
import { toApiError } from "@/lib/api/error"

import type { DocumentRole } from "@/features/documents/types/document.types"
import { useUploadDocument } from "@/features/documents/hooks/use-upload-document"
import { UploadDropzone } from "@/features/documents/components/upload-dropzone"
import { validateUploadFile, type UploadFileError } from "@/features/documents/upload-constraints"

const ROLE_LABELS: Record<DocumentRole, string> = {
  employee: "Employee",
  manager: "Manager",
  orgadmin: "Org admin",
  superadmin: "Super admin",
}

interface UploadFormState {
  file: File | null
  fileError: UploadFileError | null
  title: string
  description: string
  roles: DocumentRole[]
}

const EMPTY_FORM: UploadFormState = { file: null, fileError: null, title: "", description: "", roles: [] }

/** Contract-shaped metadata for the current form values (trimmed optional text). */
function buildMetadata(form: UploadFormState) {
  return {
    ...(form.title.trim() === "" ? {} : { title: form.title.trim() }),
    ...(form.description.trim() === "" ? {} : { description: form.description.trim() }),
    allowed_roles: form.roles,
  }
}

/**
 * Reusable upload dialog for `POST /documents/upload`.
 *
 * Lifecycle: select file → validate → select permitted roles → submit →
 * HTTP upload progress → acceptance → refresh listing (via the upload hook)
 * → navigate to the document's detail page. Submission is guarded against
 * double-submission (`isPending`) because the backend creates a new document
 * per accepted attempt. `transferPercent` is transport progress only — it is
 * never presented as document-processing progress.
 */
export function UploadDialog({
  trigger,
  open: openProp,
  onOpenChange,
  className,
}: {
  trigger?: React.ReactNode
  /** Controlled state; omitted means the dialog manages itself. */
  open?: boolean
  onOpenChange?: (open: boolean) => void
  className?: string
}) {
  const [internalOpen, setInternalOpen] = useState(false)
  const isControlled = openProp !== undefined
  const open = isControlled ? openProp : internalOpen
  const setOpen = isControlled ? (onOpenChange ?? (() => {})) : setInternalOpen

  const navigate = useNavigate()
  const upload = useUploadDocument()
  const [form, setForm] = useState<UploadFormState>(EMPTY_FORM)
  const [transferPercent, setTransferPercent] = useState<number | null>(null)

  const isSubmitting = upload.isPending

  const contractError = useMemo(() => {
    if (form.roles.length === 0) {
      return "Select at least one role who may access this document."
    }
    const parsed = uploadMetadataSchema.safeParse(buildMetadata(form))
    if (!parsed.success) {
      return "Upload metadata does not match the API contract. Check title, description, and roles."
    }
    return null
  }, [form])

  // Reset the form (and any failed mutation) whenever the dialog closes.
  useEffect(() => {
    if (!open) {
      upload.reset()
      setForm(EMPTY_FORM)
      setTransferPercent(null)
    }
    // The mutation handle is intentionally excluded: `reset` only applies on
    // close, and re-subscribing to it would re-render the form on status ticks.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  function patchForm(patch: Partial<UploadFormState>) {
    setForm((current) => ({ ...current, ...patch }))
  }

  function onTransferProgress(percent: number) {
    setTransferPercent(percent)
  }

  function onSubmit() {
    if (form.file === null || form.fileError !== null || contractError !== null || isSubmitting) return
    setTransferPercent(0)
    upload.mutate(
      {
        file: form.file,
        metadata: buildMetadata(form),
        transfer: { onProgress: onTransferProgress },
      },
      {
        onSuccess: (accepted) => {
          setOpen(false)
          navigate(`/documents/${accepted.document_id}`)
        },
      },
    )
  }

  const transferError = upload.isError ? toApiError(upload.error) : null

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {trigger !== undefined ? (
        <DialogTrigger asChild>{trigger}</DialogTrigger>
      ) : null}
      <DialogContent className={className ?? "sm:max-w-lg"} >
        <DialogHeader>
          <DialogTitle>Upload document</DialogTitle>
          <DialogDescription>
            One PDF or DOCX file up to 10 MiB. Processing starts automatically after acceptance.
          </DialogDescription>
        </DialogHeader>

        <form
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault()
            onSubmit()
          }}
        >
          <UploadDropzone file={form.file} error={form.fileError} onFileSelected={(file) => patchForm({ file, fileError: file === null ? null : validateUploadFile(file) })} disabled={isSubmitting} />
          {form.fileError ? (
            <p role="alert" className="text-xs font-medium text-destructive">
              {form.fileError.detail}
            </p>
          ) : null}

          <div className="flex flex-col gap-1.5">
            <label htmlFor="upload-title" className="text-xs font-medium text-foreground">
              Title <span className="font-normal text-muted-foreground">(optional)</span>
            </label>
            <Input
              id="upload-title"
              value={form.title}
              onChange={(event) => patchForm({ title: event.target.value })}
              placeholder="Defaults to the file name"
              maxLength={512}
              disabled={isSubmitting}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="upload-description" className="text-xs font-medium text-foreground">
              Description <span className="font-normal text-muted-foreground">(optional)</span>
            </label>
            <Textarea
              id="upload-description"
              value={form.description}
              onChange={(event) => patchForm({ description: event.target.value })}
              placeholder="What is this document for?"
              maxLength={2000}
              rows={2}
              disabled={isSubmitting}
            />
          </div>

          <fieldset className="flex flex-col gap-2">
            <legend className="mb-1 text-xs font-medium text-foreground">Allowed roles</legend>
            <span id="upload-role-hint" className="text-xs text-muted-foreground">
              Choose which roles can access this document.
            </span>
            <div className="grid grid-cols-2 gap-2" aria-describedby="upload-role-hint">
              {DOCUMENT_ROLES.map((role) => (
                <RoleCheckboxRow
                  key={role}
                  label={ROLE_LABELS[role]}
                  checked={form.roles.includes(role)}
                  onChecked={(checked) =>
                    setForm((current) => ({
                      ...current,
                      roles: checked ? [...current.roles, role] : current.roles.filter((existing) => existing !== role),
                    }))
                  }
                  disabled={isSubmitting}
                />
              ))}
            </div>
          </fieldset>

          {transferError ? (
            <Alert variant="destructive">
              <AlertDescription className="break-words">
                {transferError.detail}
                {transferError.requestId ? (
                  <span className="mt-1 block font-mono text-xs opacity-70">
                    Request ID: {transferError.requestId}
                  </span>
                ) : null}
              </AlertDescription>
            </Alert>
          ) : null}

          {transferPercent !== null && isSubmitting ? (
            <div>
              <Progress value={transferPercent} aria-label="HTTP upload progress" />
              <p className="mt-1 text-xs text-muted-foreground">
                Uploading file… {transferPercent}%
              </p>
            </div>
          ) : null}

          <DialogFooter className="gap-2">
            <DialogClose asChild>
              <Button type="button" variant="outline" disabled={isSubmitting}>
                Cancel
              </Button>
            </DialogClose>
            <Button
              type="submit"
              disabled={isSubmitting || form.file === null || form.fileError !== null || contractError !== null}
            >
              {isSubmitting ? (
                <Loader2Icon className="size-4 animate-spin" aria-hidden="true" />
              ) : (
                <UploadIcon className="size-4" aria-hidden="true" />
              )}
              {isSubmitting ? "Uploading…" : "Upload document"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}

/** Labeled checkbox row for the roles fieldset. */
function RoleCheckboxRow({
  label,
  checked,
  onChecked,
  disabled,
}: {
  label: string
  checked: boolean
  onChecked: (checked: boolean) => void
  disabled?: boolean
}) {
  const id = useId()

  return (
    <div className="flex items-center gap-2 rounded-md border border-border px-2.5 py-1.5">
      <Checkbox
        id={id}
        checked={checked}
        onCheckedChange={(value) => {
          onChecked(value === true)
        }}
        disabled={disabled}
      />
      <label htmlFor={id} className="cursor-pointer text-xs font-normal text-foreground">
        {label}
      </label>
    </div>
  )
}
