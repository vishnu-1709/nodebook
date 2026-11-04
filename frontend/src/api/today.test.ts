import { describe, expect, it } from "vitest";
import { relativeDue } from "./today";

describe("relativeDue", () => {
  const now = new Date(2026, 10, 4, 12, 0);
  it("formats relative days", () => {
    expect(relativeDue(new Date(2026, 10, 4, 17, 0).toISOString(), now)).toMatch(/^today/);
    expect(relativeDue(new Date(2026, 10, 5, 9, 0).toISOString(), now)).toMatch(/^tomorrow/);
    expect(relativeDue(new Date(2026, 10, 1, 9, 0).toISOString(), now)).toBe("3 days ago");
    expect(relativeDue(new Date(2026, 10, 20, 9, 0).toISOString(), now)).toMatch(/20/);
  });
});
