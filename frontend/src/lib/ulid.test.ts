import { describe, expect, it } from "vitest";
import { ULID_RE, ulid } from "./ulid";

describe("ulid", () => {
  it("matches the backend format and sorts by time", () => {
    const a = ulid(1_700_000_000_000);
    const b = ulid(1_700_000_000_001);
    expect(a).toMatch(ULID_RE);
    expect(a < b).toBe(true);
  });
});
