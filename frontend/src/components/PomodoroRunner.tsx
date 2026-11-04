import { useEffect, useRef } from "react";
import { api } from "../api/client";
import { fmt, remaining, resume, stop, tick, usePomodoro } from "../app/pomodoro";
import { BrainCheckView } from "./BrainCheck";
import { isTypingTarget } from "../app/shortcuts";
import { useNow } from "../app/useNow";
import { useModalLayer } from "./Modal";

let lastTyping = 0;
const NOTIFY_KEY = "nodebook.pomodoro.notify-asked";

function notify(title: string, body: string): void {
  try {
    if ("Notification" in window && Notification.permission === "granted") new Notification(title, { body, silent: true });
  } catch {
    /* ignore */
  }
}

/** Mounted once in the shell: ticks the timer, updates the tab title, logs sessions. */
export function PomodoroRunner() {
  const { s, set } = usePomodoro();
  const now = useNow(s.running);
  const baseTitle = useRef(document.title || "Nodebook");

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (isTypingTarget(e.target)) lastTyping = Date.now(); };
    window.addEventListener("keydown", onKey, true);
    return () => window.removeEventListener("keydown", onKey, true);
  }, []);

  // ask for notification permission once, the first time a timer runs
  useEffect(() => {
    if (!s.running) return;
    try {
      if ("Notification" in window && Notification.permission === "default" && !localStorage.getItem(NOTIFY_KEY)) {
        localStorage.setItem(NOTIFY_KEY, "1");
        void Notification.requestPermission();
      }
    } catch {
      /* ignore */
    }
  }, [s.running]);

  useEffect(() => {
    const typing = Date.now() - lastTyping < 3000;
    const { state, event } = tick(s, now, typing);
    if (state !== s) set(state);
    if (event === "work_done") {
      notify("Break time", "Look away from the screen for a bit.");
      if (s.startedAt) {
        void api("/sessions", { method: "POST", json: {
          started_at: new Date(s.startedAt).toISOString(), ended_at: new Date(now).toISOString(), work_min: s.workMin, completed: true,
        } }).catch(() => undefined);
      }
    }
    if (event === "break_done") notify("Break over", "Ready when you are.");
  }, [now, s, set]);

  useEffect(() => {
    document.title = s.phase === "idle" ? baseTitle.current : `${fmt(remaining(s, now))} · ${s.phase === "break" ? "Break" : "Focus"} · Nodebook`;
  }, [now, s]);

  if (s.phase === "work" && s.finishSince !== null) {
    return <div className="finish-banner" role="status">Time's up — finish your thought. Break starts in a moment.</div>;
  }
  if (s.phase === "break") return <BreakScreen />;
  return null;
}

function BreakScreen() {
  const { s, set } = usePomodoro();
  const now = useNow(true);
  useModalLayer(() => set(stop(s)));
  if (s.check) {
    return (
      <div className="break-screen" role="dialog" aria-modal="true" aria-label="Quick brain check">
        <BrainCheckView check={s.check} onDone={() => set({ ...resume(s, Date.now()), check: null })} onSkipBreak={() => set(stop(s))} />
      </div>
    );
  }
  return (
    <div className="break-screen" role="dialog" aria-modal="true" aria-label="Break">
      <p className="break-title">Break — look away from the screen for a bit</p>
      <p className="break-time mono">{fmt(remaining(s, now))}</p>
      <button className="btn" onClick={() => set(stop(s))}>Skip break</button>
    </div>
  );
}
