import "@testing-library/jest-dom/vitest"

/**
 * Shared test setup. `globals: true` lets Testing Library auto-register
 * cleanup in afterEach. jsdom lacks `scrollIntoView`, touched by
 * interactive components (dialogs, tooltips).
 */
import { beforeAll } from "vitest"

beforeAll(() => {
  if (typeof Element.prototype.scrollIntoView !== "function") {
    Element.prototype.scrollIntoView = () => {}
  }
})
