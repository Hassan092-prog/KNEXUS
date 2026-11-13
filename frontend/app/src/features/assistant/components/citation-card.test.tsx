import { describe, expect, it } from "vitest"
import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { CitationCard } from "@/features/assistant/components/citation-card"
import { renderWithProviders } from "@/test/utils"
import type { Citation } from "@/features/assistant/types/assistant.types"

/**
 * Citation card tests: the card must stay scannable (excerpt preview with a
 * Show more / Show less toggle) and must never print a placeholder for a
 * missing page number.
 */

const SHORT_EXCERPT = "Employees receive 21 days of annual leave per year."

const LONG_EXCERPT =
  "Section 4 of the employee handbook explains the annual leave entitlement. " +
  "Every full-time employee accrues twenty one days of paid annual leave per calendar year. " +
  "The entitlement may be carried over into the following year, up to five unused days. " +
  "Requests must be submitted to the line manager at least two weeks in advance."

function citation(overrides: Partial<Citation> = {}): Citation {
  return {
    id: 1,
    chunk_id: "00000000-0000-4000-8000-000000000011",
    document_id: "00000000-0000-4000-8000-000000000001",
    document_title: "Synthetic Employee Handbook",
    chunk_index: 0,
    page: 1,
    excerpt: SHORT_EXCERPT,
    similarity_score: 0.9,
    ...overrides,
  }
}

/** Matches the excerpt paragraph only (never the title or meta row). */
function excerptParagraph(): HTMLElement {
  const node = document.querySelector("p.break-words")
  if (!node) throw new Error("citation excerpt paragraph not found")
  return node as HTMLElement
}

describe("CitationCard", () => {
  it("keeps the marker, title, chunk, page and similarity visible", () => {
    renderWithProviders(<CitationCard citation={citation()} />)

    expect(screen.getByLabelText("Citation 1")).toHaveTextContent("[1]")
    expect(screen.getByText("Synthetic Employee Handbook")).toBeInTheDocument()
    expect(screen.getByText(/chunk 1/)).toBeInTheDocument()
    expect(screen.getByText(/page 1/)).toBeInTheDocument()
    expect(screen.getByText(/similarity 0\.90/)).toBeInTheDocument()
    expect(screen.getByText(SHORT_EXCERPT)).toBeInTheDocument()
  })

  it("omits the page entirely when the citation has no page", () => {
    renderWithProviders(<CitationCard citation={citation({ page: null })} />)

    // A null page (DOCX citations) is hidden, never rendered as a placeholder.
    expect(screen.queryByText(/page unavailable/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/page \d/)).not.toBeInTheDocument()
    expect(screen.getByText(/chunk 1/)).toBeInTheDocument()
    expect(screen.getByText(/similarity 0\.90/)).toBeInTheDocument()
  })

  it("previews a long excerpt and toggles the full text", async () => {
    const user = userEvent.setup()
    renderWithProviders(<CitationCard citation={citation({ excerpt: LONG_EXCERPT })} />)

    // Collapsed: a short preview, not the whole chunk.
    const preview = excerptParagraph().textContent ?? ""
    expect(preview).not.toBe(LONG_EXCERPT)
    expect(preview.length).toBeLessThanOrEqual(303)
    expect(preview.endsWith("...")).toBe(true)
    expect(screen.queryByText(LONG_EXCERPT)).not.toBeInTheDocument()

    const toggle = screen.getByRole("button", { name: "Show more" })
    await user.click(toggle)

    // Expanded: the full excerpt, exactly once.
    expect(excerptParagraph().textContent).toBe(LONG_EXCERPT)
    expect(screen.getAllByText(LONG_EXCERPT)).toHaveLength(1)

    await user.click(screen.getByRole("button", { name: "Show less" }))
    expect(excerptParagraph().textContent).not.toBe(LONG_EXCERPT)
  })

  it("does not offer a toggle for an excerpt that already fits", () => {
    renderWithProviders(<CitationCard citation={citation()} />)

    expect(screen.queryByRole("button", { name: "Show more" })).not.toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Show less" })).not.toBeInTheDocument()
    expect(screen.getByText(SHORT_EXCERPT)).toBeInTheDocument()
  })

  it("renders a citation whose page is absent without crashing", async () => {
    const user = userEvent.setup()
    renderWithProviders(<CitationCard citation={citation({ page: null, excerpt: LONG_EXCERPT })} />)

    await user.click(screen.getByRole("button", { name: "Show more" }))
    await waitFor(() => expect(excerptParagraph().textContent).toBe(LONG_EXCERPT))
    expect(screen.queryByText(/page unavailable/i)).not.toBeInTheDocument()
  })
})
