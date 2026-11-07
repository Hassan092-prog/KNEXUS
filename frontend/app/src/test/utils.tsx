import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { render } from "@testing-library/react"
import { TooltipProvider } from "@/components/ui/tooltip"
import { beforeEach } from "vitest"

import { MemoryRouter } from "react-router-dom"
import { resetMockStore } from "@/mocks/store"
import type { ReactElement } from "react"

/**
 * Shared renderer for component tests: real providers (theme, query client),
 * a fresh mock store per render, and router context. Uses the suite default
 * of no retries so failures surface immediately in assertions.
 */
export function renderWithProviders(
  ui: ReactElement,
  { initialRoute = "/" }: { initialRoute?: string } = {},
) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, refetchOnWindowFocus: false, staleTime: 0 },
      mutations: { retry: false },
    },
  })

  return {
    ...render(
      <QueryClientProvider client={queryClient}>
        <TooltipProvider>
          <MemoryRouter initialEntries={[initialRoute]}>{ui}</MemoryRouter>
        </TooltipProvider>
      </QueryClientProvider>,
    ),
    queryClient,
  }
}

/** Re-seeds the fixture-backed mock store between tests. */
export function useFreshMockStore(): void {
  beforeEach(() => {
    resetMockStore()
  })
}
