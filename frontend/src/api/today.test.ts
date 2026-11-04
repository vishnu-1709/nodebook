import { describe, expect, it } from "vitest";
import { relativeDue, weekLine } from "./today";

describe("relativeDue", () => {
  const now = new Date(2026, 10, 4, 12, 0);
  it("formats relative days", () => {
    expect(relativeDue(new Date(2026, 10, 4, 17, 0).toISOString(), now)).toMatch(/^today/);
    expect(relativeDue(new Date(2026, 10, 5, 9, 0).toISOString(), now)).toMatch(/^tomorrow/);
    expect(relativeDue(new Date(2026, 10, 1, 9, 0).toISOString(), now)).toBe("3 days ago");
    expect(relativeDue(new Date(2026, 10, 20, 9, 0).toISOString(), now)).toMatch(/20/);
  });
});

describe("weekLine", () => {
  it("summarises the week calmly", () => {
    expect(weekLine({ focus_min: 200, sessions: 8, reviews: 48, tests: 6, topics_studied: 4 })).toBe(
      "This week: 3 h 20 min focused · 48 reviews · 6 tests · 4 topics studied");
    expect(weekLine({ focus_min: 0, sessions: 0, reviews: 0, tests: 0, topics_studied: 0 })).toMatch(/nothing yet/);
  });
});
