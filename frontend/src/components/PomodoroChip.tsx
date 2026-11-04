import { useEffect, useRef, useState } from "react";
import { useSettings } from "../api/hooks";
import { fmt, pause, remaining, resume, startBreak, startWork, stop, usePomodoro } from "../app/pomodoro";
import { useNow } from "../app/useNow";

const CLOCK = (
  <svg width="16" height="16" viewBox="0 0 16 16" aria-hidden="true">
    <circle cx="8" cy="8" r="6.25" fill="none" stroke="currentColor" strokeWidth="1.5" />
    <path d="M8 4.5V8l2.5 1.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
  </svg>
);

/** Header chip (UI.md §2): clock when idle, mm:ss when running; click → popover. */
export function PomodoroChip() {
  const { s, set } = usePomodoro();
  const settings = useSettings();
  const now = useNow(s.phase !== "idle");
  const [open, setOpen] = useState(false);
  const [custom, setCustom] = useState({ work: 30, brk: 5 });
  const ref = useRef<HTMLDivElement>(null);
  const presets = settings.data?.pomodoro_presets ?? [{ work_min: 25, break_min: 5 }, { work_min: 50, break_min: 10 }];

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) setOpen(false); };
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { e.stopPropagation(); setOpen(false); } };
    window.addEventListener("mousedown", onDown);
    window.addEventListener("keydown", onKey, true);
    return () => { window.removeEventListener("mousedown", onDown); window.removeEventListener("keydown", onKey, true); };
  }, [open]);

  const left = remaining(s, now);
  const label = s.phase === "idle" ? "Pomodoro" : `${s.phase === "break" ? "Break" : "Focus"} ${fmt(left)}${s.running ? "" : " (paused)"}`;

  return (
    <div className="pomo" ref={ref}>
      <button className={s.phase === "idle" ? "pomo-chip" : "pomo-chip running"} aria-label={label} aria-expanded={open}
        title="Pomodoro (P)" onClick={() => setOpen(!open)}>
        {s.phase === "idle" ? CLOCK : <>{s.phase === "break" ? "☕" : ""}{fmt(left)}{!s.running && " ‖"}</>}
      </button>
      {open && (
        <div className="pomo-pop" role="dialog" aria-label="Pomodoro">
          {s.phase === "idle" ? (
            <>
              <p className="small muted">Start a focus block</p>
              <div className="stack-tight">
                {presets.map((p, i) => (
                  <button key={i} className="btn btn-sm" onClick={() => { set(startWork(s, Date.now(), p.work_min, p.break_min)); setOpen(false); }}>
                    {p.work_min} / {p.break_min} min
                  </button>
                ))}
              </div>
              <div className="row">
                <input className="input pomo-num" type="number" min={1} max={180} aria-label="Focus minutes" value={custom.work}
                  onChange={(e) => setCustom({ ...custom, work: Number(e.target.value) || 1 })} />
                <span className="small muted">/</span>
                <input className="input pomo-num" type="number" min={1} max={60} aria-label="Break minutes" value={custom.brk}
                  onChange={(e) => setCustom({ ...custom, brk: Number(e.target.value) || 1 })} />
                <button className="btn btn-sm" onClick={() => { set(startWork(s, Date.now(), custom.work, custom.brk)); setOpen(false); }}>Custom</button>
              </div>
            </>
          ) : (
            <>
              <p className="pomo-big mono">{fmt(left)}</p>
              <p className="small muted">{s.phase === "work" ? `Focus · ${s.workMin} min` : `Break · ${s.breakMin} min`}</p>
              <div className="row">
                <button className="btn btn-sm btn-primary" onClick={() => set(s.running ? pause(s, Date.now()) : resume(s, Date.now()))}>
                  {s.running ? "Pause" : "Resume"} <span className="kbd">P</span>
                </button>
                <button className="btn btn-sm" onClick={() => { set(s.phase === "work" ? startBreak(s, Date.now()) : stop(s)); setOpen(false); }}>Skip</button>
                <button className="btn btn-sm btn-ghost" onClick={() => { set(stop(s)); setOpen(false); }}>Stop</button>
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
}
