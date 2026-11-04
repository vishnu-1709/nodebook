/** Placeholder until M7 wires the timer; renders the idle clock chip. */
export function PomodoroChip() {
  return (
    <button className="pomo-chip" aria-label="Pomodoro timer" title="Pomodoro (P)">
      <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true"><circle cx="8" cy="8" r="6.25" fill="none" stroke="currentColor" strokeWidth="1.5" /><path d="M8 4.5V8l2.5 1.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" /></svg>
    </button>
  );
}
