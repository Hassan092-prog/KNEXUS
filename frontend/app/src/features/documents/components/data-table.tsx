import { cn } from "@/lib/utils"

/**
 * Data table structure: header row convention used by document tables.
 * Data population, sorting, filtering, and interactive pagination land in Z03.
 * Renders only column headers; body rows are added when data is available.
 *
 * The table carries no card surface or shadow — the parent layout surface
 * provides structure. Avoids nested bordered containers.
 */
export function DataTable({ headers }: { headers: string[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm text-left">
        <thead className="bg-muted/50">
          <tr className="border-b border-border">
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
