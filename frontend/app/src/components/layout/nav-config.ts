import { env } from "@/lib/env"
import {
  LayoutDashboardIcon,
  LibraryBigIcon,
  SparklesIcon,
  BookIcon,
  type LucideIcon,
} from "lucide-react"

/** Route metadata shared by the sidebar and header breadcrumbs. */

export interface NavItem {
  label: string
  to: string
  /** Match the path exactly (top-level routes). */
  end: boolean
  icon: LucideIcon
  /** Section group for sidebar rendering. */
  section?: string
  /** External link (rendered as an anchor, not a router link). */
  external?: boolean
  /** Destination for external items. */
  href?: string
}

export interface NavSection {
  key: string
  label: string
  items: NavItem[]
}

export const navItems: NavItem[] = [
  { label: "Overview", to: "/", end: true, icon: LayoutDashboardIcon, section: "workspace" },
  { label: "Documents", to: "/documents", end: false, icon: LibraryBigIcon, section: "workspace" },
  { label: "Assistant", to: "/assistant", end: false, icon: SparklesIcon, section: "workspace" },
  {
    label: "API documentation",
    to: "",
    end: false,
    icon: BookIcon,
    section: "system",
    external: true,
    href: `${env.apiBaseUrl}/docs`,
  },
]

export const navSections: NavSection[] = [
  {
    key: "workspace",
    label: "Workspace",
    items: navItems.filter((item) => item.section === "workspace"),
  },
  {
    key: "system",
    label: "System",
    items: navItems.filter((item) => item.section === "system"),
  },
]

export interface BreadcrumbItem {
  label: string
  href?: string
}

/**
 * Breadcrumb labels per path; document-id segments collapse to a generic
 * label here — the details page surfaces the real document title itself.
 */
export function resolveBreadcrumbs(pathname: string): BreadcrumbItem[] {
  if (pathname === "/") return [{ label: "Overview" }]
  if (pathname === "/documents") return [{ label: "Documents" }]
  if (pathname === "/assistant") return [{ label: "Assistant" }]
  if (pathname.startsWith("/documents/")) {
    return [
      { label: "Documents", href: "/documents" },
      { label: "Details" },
    ]
  }
  return [{ label: "Not found" }]
}
