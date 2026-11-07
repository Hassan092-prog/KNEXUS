/**
 * Centralized TanStack Query keys for the documents feature
 * (`['<feature>', '<scope>', …variables]`). Stable keys keep caching,
 * invalidation and polling correct — component code must not build keys.
 */
import type { DocumentListParams } from "@/features/documents/types/document.types"

export const documentKeys = {
  /** Root scope; invalidating this refetches every documents-related query. */
  all: ["documents"] as const,
  /**
   * Full accessible collection under the server-owned demo actor. Derived
   * views (dashboard counters, library tables) share this single query.
   */
  scan: (): readonly ["documents", "scan"] => [...documentKeys.all, "scan"] as const,
  /** Paginated server list (single limit/offset window). */
  list: (params: DocumentListParams): readonly unknown[] => [...documentKeys.all, "list", params] as const,
  detail: (documentId: string): readonly unknown[] => [...documentKeys.all, "detail", documentId] as const,
  status: (documentId: string): readonly unknown[] => [...documentKeys.all, "status", documentId] as const,
} as const
