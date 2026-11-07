"use client"

import { useCallback, useEffect, useState } from "react"

import { ThemeContext, type ThemeContextType } from "@/components/shared/theme-context"

function getStoredTheme(): ThemeContextType["theme"] {
  try {
    const stored = localStorage.getItem("knexus-theme") as ThemeContextType["theme"] | null
    if (stored === "light" || stored === "dark") return stored
  } catch {
    // localStorage may be unavailable/blocked; fall back to light.
  }
  return "light"
}

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<ThemeContextType["theme"]>(getStoredTheme)

  // Apply the .dark class on <html> so semantic tokens switch consistently.
  useEffect(() => {
    if (theme === "dark") {
      document.documentElement.classList.add("dark")
    } else {
      document.documentElement.classList.remove("dark")
    }
  }, [theme])

  const setTheme = useCallback((next: ThemeContextType["theme"]) => {
    setThemeState(next)
    try {
      localStorage.setItem("knexus-theme", next)
    } catch {
      // ignore
    }
  }, [])

  const toggleTheme = useCallback(() => {
    setTheme(theme === "light" ? "dark" : "light")
  }, [theme, setTheme])

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  )
}
