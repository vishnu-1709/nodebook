import { describe, expect, it } from "vitest";
import { drain } from "./sse";

describe("drain", () => {
  it("parses complete events and keeps the remainder", () => {
    const got: unknown[] = [];
    const rest = drain('data: {"a":1}\n\ndata: {"b":2}\n\ndata: {"c"', (e) => got.push(e));
    expect(got).toEqual([{ a: 1 }, { b: 2 }]);
    expect(rest).toBe('data: {"c"');
  });
});
