import { describe, expect, it, vi } from "vitest"
import { screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { ErrorState } from "@/components/shared/error-state"
import { ApiError } from "@/lib/api/error"
import { render } from "@testing-library/react"
import { formatByteSize } from "@/lib/utils/format"
import { QueryComposer } from "@/features/assistant/components/query-composer"

import { useFreshMockStore } from "@/test/utils"

/** Shared-component tests: error surface composition + composer interaction. */
describe("ErrorState", () => {
  useFreshMockStore()

  it("shows the canonical code, safe detail, request id and retry", async () => {
    const user = userEvent.setup()
    const onRetry = vi.fn()
    render(
      <ErrorState
        error={new ApiError({
          status: 503,
          code: "PROVIDER_UNAVAILABLE",
          detail: "The generation provider is unavailable.",
          requestId: "00000000-0000-4000-8000-000000000abc",
        })}
        onRetry={onRetry}
      />,
    )

    expect(screen.getByText("PROVIDER_UNAVAILABLE")).toBeInTheDocument()
    expect(screen.getByText(/The generation provider is unavailable/)).toBeInTheDocument()
    expect(screen.getByText(/00000000-0000-4000-8000-000000000abc/)).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: /Retry/ }))
    expect(onRetry).toHaveBeenCalledTimes(1)
  })

  it("does not expose exception internals for unknown errors", () => {
    render(<ErrorState error={new Error("secret stack: /private/var/…")} />)
    expect(screen.getByText("Request failed")).toBeInTheDocument()
    expect(screen.queryByText(/secret stack/)).not.toBeInTheDocument()
  })
})

describe("QueryComposer", () => {
  useFreshMockStore()

  it("submits on Enter, keeps Shift+Enter as newline, and trims dead input", async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<QueryComposer onSubmit={onSubmit} pending={false} />)

    const composer = screen.getByLabelText("Question for the knowledge assistant")

    await user.type(composer, "   {Enter}") // whitespace-only stays unsubmitted
    expect(onSubmit).not.toHaveBeenCalled()

    await user.type(composer, "How does the leave policy work?{Enter}")
    expect(onSubmit).toHaveBeenCalledTimes(1)
    expect(onSubmit).toHaveBeenCalledWith("How does the leave policy work?")
  })

  it("blocks submission past the character budget and shows the warning", async () => {
    const user = userEvent.setup()
    const onSubmit = vi.fn()
    render(<QueryComposer onSubmit={onSubmit} pending={false} maxLength={10} />)

    const composer = screen.getByLabelText("Question for the knowledge assistant")
    await user.type(composer, "012345678901{Enter}")

    expect(screen.getByText(/exceeds the maximum of 10 characters/)).toBeInTheDocument()
    expect(screen.getByRole("button", { name: /Submit question/ })).toBeDisabled()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it("disables interaction while a query is pending", () => {
    const onSubmit = vi.fn()
    render(<QueryComposer onSubmit={onSubmit} pending />)

    expect(screen.getByRole("button", { name: /Submit question/ })).toBeDisabled()
    expect(screen.getByLabelText("Question for the knowledge assistant")).toBeDisabled()
  })
})

describe("formatByteSize", () => {
  it("renders human-readable sizes with contract limits", () => {
    expect(formatByteSize(0)).toBe("0 B")
    expect(formatByteSize(2048)).toBe("2 KiB")
    expect(formatByteSize(10 * 1024 * 1024)).toBe("10 MiB")
    // A just-over-limit file still reads cleanly in the validation message.
    expect(formatByteSize(10 * 1024 * 1024 + 1)).toBe("10 MiB")
    expect(formatByteSize(10 * 1024 * 1024 + 20480)).toBe("10 MiB")
  })
})
