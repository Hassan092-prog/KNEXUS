/** Shared formatting helpers — stable and locale-aware across features. */

const dateTimeFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
  timeStyle: "short",
})

const dateFormatter = new Intl.DateTimeFormat(undefined, {
  dateStyle: "medium",
})

/** Formats an ISO-8601 aware timestamp for tables and detail pages. */
export function formatDateTime(isoTimestamp: string): string {
  const date = new Date(isoTimestamp)
  if (Number.isNaN(date.getTime())) return isoTimestamp
  return dateTimeFormatter.format(date)
}

/** Date-only formatting for mobile cards. */
export function formatDate(isoTimestamp: string): string {
  const date = new Date(isoTimestamp)
  if (Number.isNaN(date.getTime())) return isoTimestamp
  return dateFormatter.format(date)
}

const byteUnits = ["B", "KiB", "MiB"] as const

/** Human-readable byte size with one decimal below 10 MiB. */
export function formatByteSize(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "—"
  let value = bytes
  let unitIndex = 0
  while (value >= 1024 && unitIndex < byteUnits.length - 1) {
    value /= 1024
    unitIndex += 1
  }
  const rounded = unitIndex === 0 ? value : value >= 10 ? Math.round(value) : Math.round(value * 10) / 10
  return `${rounded} ${byteUnits[unitIndex]}`
}

/** Percent display for backend progress (`null` stays undisplayed). */
export function formatPercent(value: number | undefined): string {
  return value === undefined ? "—" : `${value}%`
}

/** Rounded cosine similarity for citation confidence display. */
export function formatSimilarity(score: number): string {
  return `sim. ${score.toFixed(2)}`
}
