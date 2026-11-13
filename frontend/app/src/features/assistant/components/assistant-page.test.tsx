import { describe, expect, it, vi } from "vitest"
import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { AssistantPage } from "@/features/assistant/components/assistant-page"
import { renderWithProviders } from "@/test/utils"

/**
 * Assistant workflow tests on the real mock API: question submission, answer
 * rendering with citations, valid 200-abstention, and provider/network error
 * surfaces.
 */

const COMPOSER_LABEL = "Question for the knowledge assistant"

async function ask(question: string) {
  const user = userEvent.setup()
  const composer = screen.getByLabelText(COMPOSER_LABEL)
  await user.type(composer, `${question}{Enter}`)
  return user
}

describe("assistant workflow", () => {
  it("answers a question with citations after loading", async () => {
    renderWithProviders(<AssistantPage />)

    expect(await screen.findByText("Ask")).toBeInTheDocument()
    await ask("How many days of annual leave are allowed?")

    // Use a more specific regex that matches the answer text "The synthetic
    // handbook allows 21 days of annual leave per year" but not the citation
    // card excerpt "Employees receive 21 days of annual leave per year."
    expect(screen.getByText(/The synthetic handbook allows 21 days/)).toBeInTheDocument()
    expect(screen.getByText("Citations (1)")).toBeInTheDocument()
    expect(screen.getByLabelText("Citation 1")).toBeInTheDocument()
    expect(screen.getByText(/similarity/)).toBeInTheDocument()
    // Meta row is backend-measured, never fabricated.
    expect(screen.getByText(/model llama3\.2:3b/)).toBeInTheDocument()
  })

  it("renders inline citation markers as references next to the answer", async () => {
    renderWithProviders(<AssistantPage />)
    await ask("annual leave?")

    // Use a more specific regex that matches only the answer text, not the
    // citation card excerpt.
    expect(screen.getByText(/The synthetic handbook allows 21 days/)).toBeInTheDocument()
    const citations = screen.getAllByText("[1]")
    expect(citations.length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText("Synthetic Employee Handbook", { selector: "p" })).toBeInTheDocument()
  })

  it("treats abstention as a valid answer, not an error", async () => {
    renderWithProviders(<AssistantPage />)
    await ask("tell me something entirely unrelated to work")

    expect(await screen.findByText("No confident answer available")).toBeInTheDocument()
    expect(screen.getByText(/knowledge base did not contain sufficiently relevant evidence/)).toBeInTheDocument()
    expect(screen.queryByText("Citations (")).not.toBeInTheDocument()
  })

  it("surfaces provider unavailability through the normalized error", async () => {
    renderWithProviders(<AssistantPage />)
    await ask("make the provider unavailable now, please")

    await waitFor(() => {
      expect(screen.getByText("PROVIDER_UNAVAILABLE")).toBeInTheDocument()
    })
    expect(screen.getByText(/The local model service is unavailable/)).toBeInTheDocument()
  })

  it("surfaces network failures as a retryable error", async () => {
    renderWithProviders(<AssistantPage />)
    await ask("cause a network failure for testing")

    await waitFor(() => {
      expect(screen.getByText("Request failed")).toBeInTheDocument()
    })
  })

  it("keeps the composer and question history in view", async () => {
    renderWithProviders(<AssistantPage />)
    await ask("first question about leave")

    // Use a more specific regex that matches only the answer text, not the
    // citation card excerpt.
    expect(screen.getByText(/The synthetic handbook allows 21 days/)).toBeInTheDocument()
    expect(screen.getByLabelText(COMPOSER_LABEL)).toBeEnabled()
    expect(screen.getByText(/Retrieval covers the assistant/)).toBeInTheDocument()
    // The submitted question stays in the thread.
    expect(screen.getByText(/first question about leave/)).toBeInTheDocument()
  })

  it("shows questions in correct order with newest just above input", async () => {
    renderWithProviders(<AssistantPage />)
    await ask("first question about leave")
    // The composer is disabled while a request is in flight; wait for it to
    // become usable again before sending the next question.
    await waitFor(() => expect(screen.getByLabelText(COMPOSER_LABEL)).toBeEnabled())
    await ask("second question about leave")

    // Questions are ordered oldest-at-top, newest-just-above-input.
    const questions = screen.getAllByText(/question about leave/)
    expect(questions.length).toBe(2)
    expect(questions.map((node) => node.textContent)).toEqual([
      "first question about leave",
      "second question about leave",
    ])
  })

  it("places the second question after the first one in the thread", async () => {
    renderWithProviders(<AssistantPage />)
    await ask("first question about leave")
    await waitFor(() => expect(screen.getByLabelText(COMPOSER_LABEL)).toBeEnabled())
    await ask("second question about leave")

    const first = screen.getByText(/first question about leave/)
    const second = screen.getByText(/second question about leave/)
    const composer = screen.getByLabelText(COMPOSER_LABEL)

    // The first question precedes the second one in document order.
    expect(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    // The newest question is rendered above the composer.
    expect(second.compareDocumentPosition(composer) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
  })

  it("scrolls the newest entry above the pinned composer when it is sent", async () => {
    const scrollIntoView = vi.spyOn(Element.prototype, "scrollIntoView")
    renderWithProviders(<AssistantPage />)
    await ask("a freshly sent question")

    await waitFor(() => expect(scrollIntoView).toHaveBeenCalled())
    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "end" })
  })

  it("scrolls again when the answer arrives so it is not hidden behind the composer", async () => {
    // Track whether a scroll happened while the answer was already rendered.
    let scrolledWithAnswerVisible = false
    const scrollIntoView = vi
      .spyOn(Element.prototype, "scrollIntoView")
      .mockImplementation(() => {
        if (screen.queryByText(/The synthetic handbook allows 21 days/)) {
          scrolledWithAnswerVisible = true
        }
      })

    renderWithProviders(<AssistantPage />)
    await ask("a question whose answer must be revealed")
    await screen.findByText(/The synthetic handbook allows 21 days/)

    // The answer lands, and the thread scrolls again to reveal it above the
    // pinned composer.
    await waitFor(() => expect(scrolledWithAnswerVisible).toBe(true))
    expect(scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "end" })
  })

  it("keeps the composer pinned to the bottom of the viewport", () => {
    renderWithProviders(<AssistantPage />)

    // The question box lives in a sticky bar so it never scrolls away.
    const composer = screen.getByLabelText(COMPOSER_LABEL)
    const stickyBar = composer.closest("div.sticky")
    expect(stickyBar).not.toBeNull()
    expect(stickyBar).toHaveClass("bottom-0")
  })
})
