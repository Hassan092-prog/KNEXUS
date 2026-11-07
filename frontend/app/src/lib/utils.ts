import { clsx } from "clsx"
import { twMerge } from "tailwind-merge"

/**
 * Combines class names using clsx and tailwind-merge.
 * Works like the original `cn` but without the `cn` package dependency.
 */
export function cn(...classes: string[]) {
  return twMerge(clsx(...classes))
}
