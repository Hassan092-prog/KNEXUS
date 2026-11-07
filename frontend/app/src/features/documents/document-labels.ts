import type {
  DocumentRole,
  DocumentSourceType,
  DocumentState,
} from "@/features/documents/types/document.types"

/** Shared display labels for document contract enums. */
export const STATUS_LABELS: Record<DocumentState, string> = {
  queued: "Queued",
  processing: "Processing",
  complete: "Complete",
  failed: "Failed",
}

export const TYPE_LABELS: Record<DocumentSourceType, string> = {
  pdf: "PDF",
  docx: "DOCX",
}

export const ROLE_LABELS: Record<DocumentRole, string> = {
  employee: "Employee",
  manager: "Manager",
  orgadmin: "Org admin",
  superadmin: "Super admin",
}
