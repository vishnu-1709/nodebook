// Orthogonal elbow connectors (UI.md §3.2): parent's right edge → horizontal stub →
// vertical trunk → horizontal stub into the child's left edge at its vertical centre.
// Paths use only M / H / V commands: no curves, no diagonals.

export interface Box {
  top: number;
  left: number;
  width: number;
  height: number;
}

export type Side = "rhs" | "lhs";

const r = (n: number) => Math.round(n) + 0.5; // crisp 2px lines on whole pixels

/** Elbow from the parent box edge to the child box edge. Children in one column share a trunk. */
export function elbow(parent: Box, child: Box, side: Side): string {
  const py = r(parent.top + parent.height / 2);
  const cy = r(child.top + child.height / 2);
  if (side === "lhs") {
    const a = parent.left;
    const b = child.left + child.width;
    return `M ${r(a)} ${py} H ${r(a - Math.max(8, (a - b) / 2))} V ${cy} H ${r(b)}`;
  }
  const a = parent.left + parent.width;
  const b = child.left;
  return `M ${r(a)} ${py} H ${r(a + Math.max(8, (b - a) / 2))} V ${cy} H ${r(b)}`;
}

/** Root → level-1. Mind-Elixir passes the topic boxes directly. */
export function mainBranch(p: { pT: number; pL: number; pW: number; pH: number; cT: number; cL: number; cW: number; cH: number; direction: string }): string {
  return elbow({ top: p.pT, left: p.pL, width: p.pW, height: p.pH }, { top: p.cT, left: p.cL, width: p.cW, height: p.cH }, p.direction === "lhs" ? "lhs" : "rhs");
}

/** Level-1+ → children. Mind-Elixir passes the `.me-parent` boxes, which pad the topic by `gap` on each side. */
export function subBranch(p: { pT: number; pL: number; pW: number; pH: number; cT: number; cL: number; cW: number; cH: number; direction: string }, gap: number): string {
  return elbow(
    { top: p.pT, left: p.pL + gap, width: p.pW - 2 * gap, height: p.pH },
    { top: p.cT, left: p.cL + gap, width: p.cW - 2 * gap, height: p.cH },
    p.direction === "lhs" ? "lhs" : "rhs",
  );
}
