import { getDataMode } from "./mode"

export function getDocumentApi() {
  return {
    listDocuments: async () => { throw new Error("Document API not available in this checkout") },
    getDocument: async () => { throw new Error("Document API not available in this checkout") },
    getDocumentStatus: async () => { throw new Error("Document API not available in this checkout") },
    uploadDocument: async () => { throw new Error("Document API not available in this checkout") },
  }
}

export function getAssistantApi() {
  return { submitQuery: async () => { throw new Error("Assistant API not available in this checkout") } }
}

export { getDataMode }
