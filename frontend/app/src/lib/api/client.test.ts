import { describe, expect, it } from "vitest"

import { apiBase, buildUploadFormData } from "@/lib/api/client"

/**
 * Request-construction tests for the shared Axios client: the `/api/v1`
 * prefix and multipart body shape (one `file`, repeated `allowed_roles`).
 */
const FILE = new File(["pdf-content"], "handbook.pdf", { type: "application/pdf" })

describe("apiBase", () => {
  it("appends the canonical /api/v1 prefix to the configured base URL", () => {
    expect(apiBase()).toMatch(/\/api\/v1$/)
    expect(apiBase()).not.toMatch(/\/api\/v1\/$/)
  })
})

describe("buildUploadFormData", () => {
  it("appends the file once and uses repeated allowed_roles fields", () => {
    const form = buildUploadFormData(FILE, {
      allowed_roles: ["employee", "manager"],
      title: "Employee Handbook",
      description: "Synthetic handbook",
    })

    expect(form.getAll("file")).toHaveLength(1)
    expect((form.get("file") as File).name).toBe("handbook.pdf")
    expect(form.getAll("allowed_roles")).toEqual(["employee", "manager"])
    expect(form.get("title")).toBe("Employee Handbook")
    expect(form.get("description")).toBe("Synthetic handbook")
  })

  it("omits unset optional metadata fields", () => {
    const form = buildUploadFormData(FILE, { allowed_roles: ["manager"] })
    expect(form.get("title")).toBeNull()
    expect(form.get("description")).toBeNull()
    expect(form.getAll("allowed_roles")).toEqual(["manager"])
  })

  it("never sends identity fields (frontend must not fabricate actor identity)", () => {
    const form = buildUploadFormData(FILE, { allowed_roles: ["employee", "orgadmin", "superadmin"] })
    for (const forbidden of ["org_id", "user_id", "role", "effective_roles", "actor"]) {
      expect(form.get(forbidden)).toBeNull()
    }
  })
})
