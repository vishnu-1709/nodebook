import type { StatusCounts } from "../api/types";

export function StatusLegend() {
  return (
    <div className="legend" aria-hidden="true">
      <span><i className="sb-got" />Got it</span>
      <span><i className="sb-revising" />Revising</span>
      <span><i className="sb-confused" />Confused</span>
      <span><i className="sb-none" />Not started</span>
    </div>
  );
}

/** Stacked status bar (UI.md §3.1): got / revising / confused / not started. */
export function StatusBar({ c }: { c: StatusCounts | undefined }) {
  if (!c || c.total === 0) return <div className="status-bar" role="img" aria-label="Not started" />;
  const pct = (n: number) => `${(n / c.total) * 100}%`;
  const label = `${c.got_it} got it, ${c.revising} revising, ${c.confused} confused, ${c.not_started} not started`;
  return (
    <div className="status-bar" role="img" aria-label={label} title={label}>
      <span className="sb-got" style={{ width: pct(c.got_it) }} />
      <span className="sb-revising" style={{ width: pct(c.revising) }} />
      <span className="sb-confused" style={{ width: pct(c.confused) }} />
      <span className="sb-none" style={{ width: pct(c.not_started) }} />
    </div>
  );
}
