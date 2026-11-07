import { describe, expect, it } from "vitest"
import { Route, Routes } from "react-router-dom"
import { screen } from "@testing-library/react"

import { DocumentDetailPage } from "@/features/documents/components/document-detail-page"
import { CANONICAL_DETAIL } from "@/mocks/store"
import { renderWithProviders } from "@/test/utils"

const CANONICAL_ID = CANONICAL_DETAIL.id
const FAILED_ID = "00000000-0000-4000-8000-000000000005"
const UNKNOWN_ID = "10000000-0000-4000-8000-000000000099"

function renderDetail(documentId: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/documents/:documentId" element={<DocumentDetailPage />} />
    </Routes>,
    { initialRoute: `/documents/${documentId}` },
  )
}

describe("document detail page", () => {
  it("renders document information from the detail endpoint", async () => {
    renderDetail(CANONICAL_ID)

    
    // Allowed roles and metadata appear from the detail endpoint only.
    expect(await screen.findByText("Allowed roles")).toBeInTheDocument()
    expect(screen.getByText("Allowed roles")).toBeInTheDocument()
    expect(screen.getByText("Metadata")).toBeInTheDocument()
  })

  it("shows terminal processing status with backend-provided progress", async () => {
    renderDetail(CANONICAL_ID)

    expect(await screen.findByText("Processing")).toBeInTheDocument()
    expect(await screen.findByText("Complete")).toBeInTheDocument()
    expect(await screen.findByText("100% of chunks processed")).toBeInTheDocument()
  })

  it("renders failed processing with the safe failure code and message", async () => {
    renderDetail(FAILED_ID)

    expect(await screen.findByText("Processing failed (INVALID_FILE)")).toBeInTheDocument()
    expect(
      await screen.findByText(/No readable text could be extracted/),
    ).toBeInTheDocument()
  })

  it("surfaces NOT_FOUND for unknown documents with a route back", async () => {
    renderDetail(UNKNOWN_ID)

    expect(await screen.findByText("Document not found")).toBeInTheDocument()
    expect(screen.getByRole("link", { name: /Back to the document library/ })).toBeInTheDocument()
  })
})
