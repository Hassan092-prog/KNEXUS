import { Link, NavLink } from "react-router-dom"
import { BookOpenCheckIcon } from "lucide-react"
import { cn } from "@/lib/utils"

import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { navSections } from "@/components/layout/nav-config"
import { getDataMode } from "@/lib/api"

function BrandMark() {
  return (
    <Link
      to="/"
      className="flex items-center gap-2 rounded-md px-2 py-1.5 outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <span className="flex size-9 items-center justify-center rounded-lg bg-primary text-primary-foreground">
        <BookOpenCheckIcon className="size-4" aria-hidden="true" />
      </span>
      <span className="flex flex-col leading-tight">
        <span className="font-heading text-sm font-semibold tracking-tight text-foreground">
          KNEXUS
        </span>
        <span className="text-[11px] text-muted-foreground">Enterprise knowledge</span>
      </span>
    </Link>
  )
}

function SectionHeading({ label }: { label: string }) {
  return (
    <h2 className="px-2.5 pt-1 pb-1 text-[10px] font-semibold tracking-wider text-muted-foreground uppercase">
      {label}
    </h2>
  )
}

function SidebarNavLinks({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav aria-label="Primary" className="flex flex-col gap-0.5">
      {navSections.map((section) => {
        if (section.items.length === 0) return null
        return (
          <div key={section.key} className="flex flex-col gap-0.5">
            <SectionHeading label={section.label} />
            {section.items.map((item) => {
              const Icon = item.icon
              if (item.external) {
                return (
                  <a
                    key={item.label}
                    href={item.href}
                    target="_blank"
                    rel="noreferrer"
                    onClick={onNavigate}
                    className="flex items-center gap-2 rounded-md px-2.5 py-2 text-sm font-medium text-sidebar-foreground outline-none transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <Icon className="size-4 shrink-0" aria-hidden="true" />
                    <span className="truncate">{item.label}</span>
                  </a>
                )
              }
              return (
                <NavLink
                  key={item.label}
                  to={item.to}
                  end={item.end}
                  onClick={onNavigate}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-2 rounded-md border-l-2 border-transparent px-2.5 py-2 text-sm font-medium outline-none transition-colors",
                      "focus-visible:ring-2 focus-visible:ring-ring",
                      isActive
                        ? "bg-sidebar-accent text-sidebar-accent-foreground border-sidebar-primary"
                        : "text-sidebar-foreground hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
                    )
                  }
                >
                  <Icon className="size-4 shrink-0" aria-hidden="true" />
                  <span className="truncate">{item.label}</span>
                </NavLink>
              )
            })}
          </div>
        )
      })}
    </nav>
  )
}

function SidebarFooterNote() {
  const mode = getDataMode()

  return (
    <div className="mt-auto rounded-lg border border-sidebar-border bg-sidebar/50 p-3 text-xs text-sidebar-foreground">
      <p className="flex items-center gap-2 font-medium text-sidebar-foreground">
        <span
          aria-hidden="true"
          className={
            mode === "mock"
              ? "size-1.5 rounded-full bg-sidebar-foreground/50"
              : "size-1.5 rounded-full bg-emerald-500"
          }
        />
        {mode === "mock" ? "Mock data mode" : "Live API mode"}
      </p>
      <p className="mt-1 text-[10px] text-sidebar-foreground/60 leading-relaxed">
        {mode === "mock"
          ? "Local JSON fixtures; no backend requests."
          : "Requests go to the configured KNEXUS backend."}
      </p>
    </div>
  )
}

function SidebarBody({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <div className="flex h-full flex-col gap-6 p-4">
      <BrandMark />
      <SidebarNavLinks onNavigate={onNavigate} />
      <div className="mt-auto">
        <SidebarFooterNote />
      </div>
    </div>
  )
}

/**
 * Persistent navigation sidebar (`lg` breakpoint and above) composed with a
 * Radix-powered Sheet drawer for smaller screens. The static aside is
 * `lg:flex hidden`, while the Sheet is manually controlled from the header's
 * menu button.
 */
export function AppSidebar({
  mobileOpen,
  onMobileOpenChange,
}: {
  mobileOpen: boolean
  onMobileOpenChange: (open: boolean) => void
}) {
  return (
    <>
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[248px] border-r border-sidebar-border bg-sidebar lg:block">
        <SidebarBody />
      </aside>

      <Sheet open={mobileOpen} onOpenChange={onMobileOpenChange}>
        <SheetContent
          side="left"
          className="w-72 gap-0 border-sidebar-border bg-sidebar p-0 lg:hidden"
          aria-label="Navigation menu"
        >
          <SheetHeader className="sr-only">
            <SheetTitle>KNEXUS navigation</SheetTitle>
            <SheetDescription>Primary application navigation</SheetDescription>
          </SheetHeader>
          <SidebarBody onNavigate={() => onMobileOpenChange(false)} />
        </SheetContent>
      </Sheet>
    </>
  )
}
