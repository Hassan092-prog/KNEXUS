/**
 * Consistent page container used by every routed page.
 * Centers content, applies the standard max-width and padding, and keeps the
 * page layout convention uniform across features.
 */
export function PageContainer({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      {children}
    </div>
  )
}
