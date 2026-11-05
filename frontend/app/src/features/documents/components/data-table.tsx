import { cn } from "@/lib/utils"

/**
 * Data table structure: header row convention used by document tables.
 * Data population, sorting, filtering, and interactive pagination land in Z03.
 * Renders only column headers; body rows are added when data is available.
 */
export function DataTable({ headers }: { headers: string[] }) {
  return (
    <div className="rounded-xl border border-border bg-card overflow-hidden shadow-sm">
      <table className="w-full text-sm text-left">
        <thead className="bg-muted/50">
          <tr>
            {headers.map((header, index) => (
              <th
                key={index}
                className={cn(
                  "px-4 py-3 font-medium text-muted-foreground uppercase text-[10px] tracking-wider",
                  index === headers.length - 1 ? "text-right" : "",
                )}
              >
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody />
      </table>
    </div>
  )
}
