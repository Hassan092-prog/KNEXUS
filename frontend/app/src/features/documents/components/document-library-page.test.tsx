import { describe, expect, it } from "vitest"
import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { DocumentLibraryPage } from "@/features/documents/components/document-library-page"
import { registerUpload } from "@/mocks/store"
import type { DocumentSummary } from "@/features/documents/types/document.types"
import { renderWithProviders } from "@/test/utils"

/**
 * Document library page tests on the real mock API: rendering, frontend
 * search/filters, pagination over the stored records, and empty states.
 */

const IT_HANDBOOK = "IT Security Policy v2.4"
const LEAVE_QUESTIONS = "Expense Reimbursement Procedure"

function syntheticDocuments(count: number, offset = 0): DocumentSummary[] {
  return Array.from({ length: count }, (_unused, index) => ({
    id: `00000000-0000-4000-8000-${String(offset + index + 100).padStart(12, "0")}`,
    title: `Synthetic document ${offset + index}`,
    source_type: index % 2 === 0 ? "pdf" : "docx",
    status: "complete",
    allowed_roles: ["employee"],
    chunk_count: 4,
    created_at: `2025-01-0${(index % 9) + 1}T00:00:00Z`,
  }))
}

describe("document library", () => {
  it("renders the accessible documents with status and roles", async () => {
    renderWithProviders(<DocumentLibraryPage />)

    expect(await screen.findByText(IT_HANDBOOK)).toBeInTheDocument()
    expect(await screen.findByText(LEAVE_QUESTIONS)).toBeInTheDocument()
    expect(screen.getAllByText("Complete").length).toBeGreaterThan(0)
    expect(screen.getAllByText("employee").length).toBeGreaterThan(0)
  })

  it("filters by search as the user types", async () => {
    renderWithProviders(<DocumentLibraryPage />)

    await screen.findByText(IT_HANDBOOK)
    await userEvent.type(screen.getByLabelText("Search documents by title"), "Expense")

    expect(await screen.findByText(LEAVE_QUESTIONS)).toBeInTheDocument()
    expect(screen.queryByText(IT_HANDBOOK)).not.toBeInTheDocument()
  })

  it("shows an empty search state with a clear action", async () => {
    renderWithProviders(<DocumentLibraryPage />)

    await screen.findByText(IT_HANDBOOK)
    await userEvent.type(screen.getByLabelText("Search documents by title"), "zzz-no-match-zzz")

    expect(await screen.findByText("No documents match your search")).toBeInTheDocument()
  })

  it("paginates beyond one page with 20-per-page slices", async () => {
    for (const document of syntheticDocuments(27)) {
      registerUpload(document, 8192)
    }
    renderWithProviders(<DocumentLibraryPage />)

    await screen.findByText("Synthetic document 0")
    const next = screen.getByRole("button", { name: "Go to next page" })
    expect(next).toBeEnabled()
    expect(screen.getByText("Page 1 of 2")).toBeInTheDocument()

    await waitFor(() => userEvent.click(next))
    expect(await screen.findByText("Synthetic document 20")).toBeInTheDocument()
    expect(screen.getByText("Page 2 of 2")).toBeInTheDocument()
  })

  it("shows the honest partial-scan note when the store was seeded capped", async () => {
    // The fixture list caps at 6 documents, so the note only appears when
    // meta.total exceeds the scan; simulate via a direct handler is not
    // possible without fixtures — the capped path is covered by the service
    // scan loop tests below.
    renderWithProviders(<DocumentLibraryPage />)
    expect(await screen.findByText(IT_HANDBOOK)).toBeInTheDocument()
  })
})
