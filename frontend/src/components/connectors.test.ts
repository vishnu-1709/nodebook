import { describe, expect, it } from "vitest";
import { elbow, mainBranch, subBranch } from "./connectors";

const ONLY_ORTHOGONAL = /^M [\d.]+ [\d.]+ H [\d.]+ V [\d.]+ H [\d.]+$/;

describe("connectors", () => {
  it("draws a right-side elbow: stub, trunk, stub into the child's left edge centre", () => {
    const d = elbow({ top: 100, left: 0, width: 140, height: 40 }, { top: 0, left: 200, width: 120, height: 30 }, "rhs");
    expect(d).toMatch(ONLY_ORTHOGONAL);
    expect(d).toBe("M 140.5 120.5 H 170.5 V 15.5 H 200.5");
  });

  it("children in one column share the same trunk x", () => {
    const parent = { top: 100, left: 0, width: 140, height: 40 };
    const a = elbow(parent, { top: 0, left: 200, width: 80, height: 30 }, "rhs");
    const b = elbow(parent, { top: 300, left: 200, width: 160, height: 30 }, "rhs");
    expect(a.split(" ")[5]).toBe(b.split(" ")[5]);
  });

  it("mirrors on the left side and never emits curves", () => {
    const d = elbow({ top: 100, left: 400, width: 140, height: 40 }, { top: 0, left: 200, width: 120, height: 30 }, "lhs");
    expect(d).toMatch(ONLY_ORTHOGONAL);
    expect(d.startsWith("M 400.5")).toBe(true);
    expect(d.endsWith("H 320.5")).toBe(true);
  });

  it("main and sub branch adapters keep to M/H/V", () => {
    const p = { pT: 0, pL: 0, pW: 100, pH: 40, cT: 80, cL: 160, cW: 100, cH: 30, direction: "rhs" };
    expect(mainBranch(p)).toMatch(ONLY_ORTHOGONAL);
    const s = subBranch(p, 24);
    expect(s).toMatch(ONLY_ORTHOGONAL);
    expect(s.startsWith("M 76.5")).toBe(true); // parent topic right edge = 0 + 100 - 24
    expect(s.endsWith("H 184.5")).toBe(true); // child topic left edge = 160 + 24
    expect(/[CQSAL]/.test(mainBranch(p) + s)).toBe(false);
  });
});
