"use client"

import { useCallback, useEffect, useState } from "react"

import { ThemeContext, type ThemeContextType } from "@/components/shared/theme-context"

function getStoredTheme(): ThemeContextType["theme"] {
  const stored = localStorage.getItem("knexus-theme") as ThemeContextType["theme"] | null
  return stored ?? "light"
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
    localStorage.setItem("knexus-theme", next)
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
