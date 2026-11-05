import { SunIcon, MoonIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import { useTheme } from "@/components/shared/use-theme"

/**
 * Light/dark theme toggle. Persists the user's selection in localStorage and
 * applies the `.dark` class on `<html>` so semantic tokens switch consistently
 * across the entire application.
 */
export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme()

  return (
    <Button
      variant="outline"
      size="icon"
      onClick={toggleTheme}
      aria-label={theme === "light" ? "Switch to dark theme" : "Switch to light theme"}
      className="shrink-0"
    >
      {theme === "light" ? (
        <>
          <MoonIcon className="size-4" aria-hidden="true" />
          <span className="sr-only">Switch to dark theme</span>
        </>
      ) : (
        <>
          <SunIcon className="size-4" aria-hidden="true" />
          <span className="sr-only">Switch to light theme</span>
        </>
      )}
    </Button>
  )
}
