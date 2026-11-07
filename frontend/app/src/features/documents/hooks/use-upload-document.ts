import { useMutation, useQueryClient } from "@tanstack/react-query"

import { getDocumentApi } from "@/lib/api"
import type { UploadMetadataInput } from "@/features/documents/types/document.types"
import type { UploadTransferOptions } from "@/features/documents/services/document.api"
import { documentKeys } from "@/features/documents/hooks/query-keys"

/**
 * Upload mutation for `POST /documents/upload`. The backend creates a new
 * document for every accepted attempt (no dedup), so the dialog forbids
 * double-submission while the request is active (`isPending`).
 *
 * On acceptance, all documents-derived queries are invalidated so the
 * dashboard and library reflect the queued document immediately; the
 * dialog navigates to the new document's detail page for processing status.
 */
export function useUploadDocument() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({ file, metadata, transfer }: { file: File; metadata: UploadMetadataInput; transfer?: UploadTransferOptions }) =>
      getDocumentApi().uploadDocument(file, metadata, transfer),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: documentKeys.all })
    },
  })
}
