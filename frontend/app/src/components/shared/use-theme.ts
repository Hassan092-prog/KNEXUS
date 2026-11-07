import { useContext } from "react"

import { ThemeContext } from "@/components/shared/theme-context"
import type { ThemeContextType } from "@/components/shared/theme-context"

/**
 * Consumes the theme context. Must be used within a ThemeProvider.
 */
export function useTheme(): ThemeContextType {
  const context = useContext(ThemeContext)
  if (context === undefined) {
    throw new Error("useTheme must be used within a ThemeProvider")
  }
  return context
}
