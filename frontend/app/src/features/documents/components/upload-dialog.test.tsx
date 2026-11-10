import { describe, expect, it, vi } from "vitest"
import { screen, waitFor, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

import { UploadDialog } from "@/features/documents/components/upload-dialog"
import { renderWithProviders, useFreshMockStore } from "@/test/utils"

/** `useNavigate` is asserted instead of actually switching routes. */
const navigateMock = vi.fn()
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>()
  return { ...actual, useNavigate: () => navigateMock }
})

const VALID_PDF = new File(["valid"], "handbook.pdf", { type: "application/pdf" })
const INVALID_TXT = new File(["nope"], "notes.txt", { type: "text/plain" })

async function openDialog(triggerLabel: string) {
  const user = userEvent.setup()
  await user.click(screen.getByRole("button", { name: triggerLabel }))
  await screen.findByRole("dialog", { name: "Upload document" })
  return user
}

async function pickFile(user: ReturnType<typeof userEvent.setup>, file: File) {
  const input = document.querySelector('input[type="file"]')
  if (!(input instanceof HTMLInputElement)) throw new Error("file input missing")
  await user.upload(input, file)
}

describe("upload dialog", () => {
  useFreshMockStore()

  it("blocks submission without a file or role", async () => {
    renderWithProviders(<UploadDialog trigger={<button type="button">Upload document</button>} />)
    const user = await openDialog("Upload document")

    const submit = screen.getByRole("button", { name: /Upload document/ })
    expect(submit).toBeDisabled()

    await pickFile(user, VALID_PDF)
    expect(screen.getByRole("button", { name: /Upload document/ })).toBeDisabled()

    await user.click(screen.getByRole("checkbox", { name: "Employee" }))
    await waitFor(() => {
      expect(screen.getByRole("button", { name: /Upload document/ })).toBeEnabled()
    })
  })

  it("rejects unsupported file formats before any request", async () => {
    renderWithProviders(<UploadDialog trigger={<button type="button">Upload document</button>} />)
    // applyAccept: false bypasses the file input's `accept` list so the
    // .txt file actually reaches the component's own validation (the
    // browser-level accept filter would silently drop it).
    const user = userEvent.setup({ applyAccept: false })
    await user.click(screen.getByRole("button", { name: "Upload document" }))
    await screen.findByRole("dialog", { name: "Upload document" })

    await pickFile(user, INVALID_TXT)
    // Both the dropzone hint and the dialog alert show the validation error.
    const errorTexts = await screen.findAllByText(
      /Unsupported file format. Only PDF and DOCX files are accepted/,
    )
    expect(errorTexts.length).toBeGreaterThanOrEqual(1)
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it("rejects files over the 10 MiB limit", async () => {
    renderWithProviders(<UploadDialog trigger={<button type="button">Upload document</button>} />)
    const user = await openDialog("Upload document")

    const tooLarge = new File(["x"], "huge.pdf", { type: "application/pdf" })
    Object.defineProperty(tooLarge, "size", { value: 10 * 1024 * 1024 + 1 })
    await pickFile(user, tooLarge)

    expect(
      (await screen.findAllByText(/File is too large .+ limit is 10 MiB/)).length,
    ).toBeGreaterThanOrEqual(1)
    expect(navigateMock).not.toHaveBeenCalled()
  })

  it("submits a valid upload and navigates to the new document", async () => {
    renderWithProviders(<UploadDialog trigger={<button type="button">Upload document</button>} />)
    const user = await openDialog("Upload document")

    await pickFile(user, VALID_PDF)
    await user.type(screen.getByLabelText(/Title/), "Vacation handbook")
    await user.click(screen.getByRole("checkbox", { name: "Employee" }))
    await user.click(screen.getByRole("checkbox", { name: "Manager" }))

    await user.click(screen.getByRole("button", { name: /Upload document/ }))

    // Mock-mode processing acceptance: navigation to the detail route.
    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledTimes(1)
    })
    const target = String(navigateMock.mock.calls[0][0])
    expect(target).toMatch(/^\/documents\/[0-9a-f-]{36}$/)
  })

  it("requires at least one role (contract minimum)", async () => {
    renderWithProviders(<UploadDialog trigger={<button type="button">Upload document</button>} />)
    const user = await openDialog("Upload document")

    await pickFile(user, VALID_PDF)
    const fieldset = screen.getByText("Allowed roles").closest("fieldset")
    expect(fieldset).not.toBeNull()

    const hint = within(fieldset as HTMLElement).getByText("Choose which roles can access this document.")
    expect(hint).toBeInTheDocument()
    expect(navigateMock).not.toHaveBeenCalled()
  })
})
