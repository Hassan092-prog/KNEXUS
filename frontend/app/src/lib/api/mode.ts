export type DataMode = "mock" | "live"
export function getDataMode(): DataMode {
  return (import.meta.env.VITE_DATA_MODE as string) === "live" ? "live" : "mock"
}
