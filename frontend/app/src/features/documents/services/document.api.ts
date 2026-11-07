import type { DocumentDetail, DocumentListParams, DocumentListResponse, DocumentStatusResponse, UploadAcceptedResponse, UploadMetadataInput } from "@/features/documents/types/document.types"

/** Optional transport-level upload reporting (HTTP progress, not processing). */
export interface UploadTransferOptions {
  /** 0–100 percentage of HTTP bytes sent; delays vary by connection. */
  onProgress?: (percent: number) => void
}

/**
 * Shared document service interface (Z02 boundary).
 *
 * Consumers (hooks/components) bind to this interface only. Whether the
 * backing implementation is the live KNEXUS endpoint or the canonical-fixture
 * mock is decided by `lib/api/index.ts` from `VITE_DATA_MODE`.
 */
export interface DocumentApi {
  listDocuments(params?: DocumentListParams): Promise<DocumentListResponse>
  getDocument(documentId: string): Promise<DocumentDetail>
  getDocumentStatus(documentId: string): Promise<DocumentStatusResponse>
  /** One PDF/DOCX file with repeated `allowed_roles` roles; no identity fields. */
  uploadDocument(
    file: File,
    metadata: UploadMetadataInput,
    options?: UploadTransferOptions,
  ): Promise<UploadAcceptedResponse>
}
