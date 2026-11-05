import { QueryClient, QueryClientProvider } from "@tanstack/react-query"

import { ThemeProvider } from "@/components/shared/theme-provider"

/**
 * Single TanStack Query client for server-state. Query keys follow the
 * convention `['<feature>', '<scope>', …variables]`.
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Failures are surfaced as ErrorState with an explicit retry — no silent retries.
      retry: false,
      refetchOnWindowFocus: false,
    },
  },
})

export function AppProviders({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>{children}</ThemeProvider>
    </QueryClientProvider>
  )
}
