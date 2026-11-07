import "@testing-library/jest-dom/vitest"

/**
 * Shared test setup. `globals: true` lets Testing Library auto-register
 * cleanup in afterEach. jsdom lacks `scrollIntoView`, touched by
 * interactive components (dialogs, tooltips).
 * Set viewport width so CSS breakpoint classes (lg:) resolve predictably
 * in tests — mirrors a 1440px desktop viewport.
 */
import { beforeAll } from "vitest"

beforeAll(() => {
  if (typeof Element.prototype.scrollIntoView !== "function") {
    Element.prototype.scrollIntoView = () => {}
  }
  Object.defineProperty(window, "innerWidth", { value: 1440, configurable: true })
})
