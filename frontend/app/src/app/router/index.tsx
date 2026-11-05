import { createBrowserRouter } from "react-router-dom"

import { RootLayout } from "@/app/layouts/root-layout"
import { NotFoundPage } from "@/app/router/not-found-page"
import { DashboardPage } from "@/features/dashboard/components/dashboard-page"
import { DocumentLibraryPage } from "@/features/documents/components/document-library-page"
import { DocumentDetailPage } from "@/features/documents/components/document-detail-page"
import { AssistantPage } from "@/features/assistant/components/assistant-page"

/**
 * Initial Phase 1 routes. Workflow features ship in later phases —
 * these routes establish the shell structure only.
 */
export const router = createBrowserRouter([
  {
    element: <RootLayout />,
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "documents", element: <DocumentLibraryPage /> },
      { path: "documents/:documentId", element: <DocumentDetailPage /> },
      { path: "assistant", element: <AssistantPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
])
