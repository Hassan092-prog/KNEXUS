import { formatByteSize } from "@/lib/utils/format"

/**
 * Upload constraint + validation mirroring the backend's upload checks
 * (`MAX_UPLOAD_BYTES` = 10 MiB, PDF/DOCX only). Client-side checks make the
 * form fail fast; the backend remains authoritative.
 */

export const MAX_UPLOAD_BYTES = 10 * 1024 * 1024

export const ACCEPTED_EXTENSIONS = [".pdf", ".docx"] as const

/** `accept` hint for the file input (extensions + registered DOCX MIME type). */
export const ACCEPT_ATTRIBUTE = ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"

export type UploadFileError =
  | { kind: "unsupported"; detail: string }
  | { kind: "too_large"; detail: string }

export function validateUploadFile(file: File): UploadFileError | null {
  const hasValidExtension = ACCEPTED_EXTENSIONS.some((accepted) =>
    file.name.toLowerCase().endsWith(accepted),
  )
  if (!hasValidExtension) {
    const extension = file.name.includes(".") ? `“${file.name.replace(/^.*\./, "")}”` : "no extension"
    return {
      kind: "unsupported",
      detail: `Unsupported file format. Only PDF and DOCX files are accepted (received ${extension}).`,
    }
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return {
      kind: "too_large",
      detail: `File is too large (${formatByteSize(file.size)}). The limit is 10 MiB.`,
    }
  }
  return null
}
