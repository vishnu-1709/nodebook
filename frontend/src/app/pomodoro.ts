import { create } from "zustand";

// Pomodoro (SPEC §5.11, UI.md §2/§3.9). Pure transition logic + a persisted store.

export type Phase = "idle" | "work" | "break";

export interface PomoState {
  phase: Phase;
  running: boolean;
  endsAt: number | null; // epoch ms while running
  remainingMs: number; // while paused
  workMin: number;
  breakMin: number;
  startedAt: number | null; // start of the current work block
  finishSince: number | null; // work ended while typing → "finish your thought"
}

export const FINISH_GRACE_MS = 60_000;
export const IDLE: PomoState = {
  phase: "idle", running: false, endsAt: null, remainingMs: 25 * 60_000, workMin: 25, breakMin: 5, startedAt: null, finishSince: null,
};

export function remaining(s: PomoState, now: number): number {
  if (s.phase === "idle") return s.workMin * 60_000;
  if (s.running && s.endsAt !== null) return Math.max(0, s.endsAt - now);
  return s.remainingMs;
}

export function startWork(s: PomoState, now: number, workMin = s.workMin, breakMin = s.breakMin): PomoState {
  return { ...s, phase: "work", running: true, workMin, breakMin, endsAt: now + workMin * 60_000, remainingMs: workMin * 60_000, startedAt: now, finishSince: null };
}

export function pause(s: PomoState, now: number): PomoState {
  if (!s.running) return s;
  return { ...s, running: false, remainingMs: remaining(s, now), endsAt: null };
}

export function resume(s: PomoState, now: number): PomoState {
  if (s.running || s.phase === "idle") return s;
  return { ...s, running: true, endsAt: now + s.remainingMs };
}

/** P: start when idle, else pause/resume. */
export function toggle(s: PomoState, now: number): PomoState {
  if (s.phase === "idle") return startWork(s, now);
  return s.running ? pause(s, now) : resume(s, now);
}

export function startBreak(s: PomoState, now: number): PomoState {
  return { ...s, phase: "break", running: true, endsAt: now + s.breakMin * 60_000, remainingMs: s.breakMin * 60_000, finishSince: null };
}

export function stop(s: PomoState): PomoState {
  return { ...IDLE, workMin: s.workMin, breakMin: s.breakMin, remainingMs: s.workMin * 60_000 };
}

export type PomoEvent = "work_done" | "break_done";

/** Advance time. Never interrupts typing: if the user is typing when work ends, wait up to 60 s. */
export function tick(s: PomoState, now: number, typing: boolean): { state: PomoState; event: PomoEvent | null } {
  if (!s.running || s.endsAt === null || now < s.endsAt) return { state: s, event: null };
  if (s.phase === "work") {
    if (s.finishSince === null && typing) return { state: { ...s, finishSince: now }, event: null };
    if (s.finishSince !== null && typing && now - s.finishSince < FINISH_GRACE_MS) return { state: s, event: null };
    return { state: startBreak(s, now), event: "work_done" };
  }
  if (s.phase === "break") return { state: stop(s), event: "break_done" };
  return { state: s, event: null };
}

export function fmt(ms: number): string {
  const total = Math.ceil(ms / 1000);
  const m = Math.floor(total / 60);
  const sec = total % 60;
  return `${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
}

const KEY = "nodebook.pomodoro";

function load(): PomoState {
  try {
    const raw = localStorage.getItem(KEY);
    if (raw) return { ...IDLE, ...(JSON.parse(raw) as Partial<PomoState>) };
  } catch {
    /* ignore */
  }
  return IDLE;
}

interface Store {
  s: PomoState;
  set: (s: PomoState) => void;
}

export const usePomodoro = create<Store>((set) => ({
  s: load(),
  set: (s) => {
    try {
      localStorage.setItem(KEY, JSON.stringify(s));
    } catch {
      /* ignore */
    }
    set({ s });
  },
}));
