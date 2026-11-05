import { Link, useLocation } from "react-router-dom"
import { MenuIcon } from "lucide-react"

import { Button } from "@/components/ui/button"
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from "@/components/ui/breadcrumb"
import { resolveBreadcrumbs } from "@/components/layout/nav-config"
import { ThemeToggle } from "@/components/shared/theme-toggle"
import { env } from "@/lib/env"

/**
 * Header with page-context breadcrumbs, a mobile navigation drawer trigger,
 * theme toggle, and one real developer utility link. No simulated user /
 * profile area — authentication is out of scope for Phase 1.
 */
export function AppHeader({
  onNavOpen,
}: {
  onNavOpen: () => void
}) {
  const { pathname } = useLocation()
  const breadcrumbs = resolveBreadcrumbs(pathname)

  return (
    <header className="sticky top-0 z-20 flex h-12 items-center gap-2 border-b border-border bg-background/95 px-3 backdrop-blur supports-[backdrop-filter]:bg-background/80 sm:px-4 lg:px-6">
      <Button
        variant="ghost"
        size="icon"
        onClick={onNavOpen}
        className="lg:hidden"
        aria-label="Open navigation menu"
      >
        <MenuIcon className="size-4" aria-hidden="true" />
      </Button>

      <Breadcrumb>
        <BreadcrumbList>
          {breadcrumbs.map((crumb, index) => {
            const isLast = index === breadcrumbs.length - 1
            return (
              <BreadcrumbItem key={`${crumb.label}-${index}`}>
                {isLast || !crumb.href ? (
                  <BreadcrumbPage className="text-[10px] font-medium text-muted-foreground">
                    {crumb.label}
                  </BreadcrumbPage>
                ) : (
                  <BreadcrumbLink asChild>
                    <Link
                      to={crumb.href}
                      className="text-[10px] font-medium text-muted-foreground hover:text-foreground transition-colors"
                    >
                      {crumb.label}
                    </Link>
                  </BreadcrumbLink>
                )}
                {!isLast ? (
                  <BreadcrumbSeparator className="size-3.5 text-muted-foreground/50" />
                ) : null}
              </BreadcrumbItem>
            )
          })}
        </BreadcrumbList>
      </Breadcrumb>

      <div className="ml-auto flex items-center gap-2">
        <ThemeToggle />
        <a
          href={`${env.apiBaseUrl}/docs`}
          target="_blank"
          rel="noreferrer"
          className="rounded-md text-xs text-muted-foreground outline-none transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring px-2 py-1"
        >
          API docs
        </a>
      </div>
    </header>
  )
}
