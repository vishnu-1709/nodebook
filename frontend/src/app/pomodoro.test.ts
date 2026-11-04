import { describe, expect, it } from "vitest";
import { FINISH_GRACE_MS, IDLE, fmt, pause, remaining, resume, startWork, tick, toggle } from "./pomodoro";

const T0 = 1_000_000;
const MIN = 60_000;

describe("pomodoro", () => {
  it("starts, pauses and resumes with the right remaining time", () => {
    let s = toggle(IDLE, T0);
    expect(s.phase).toBe("work");
    expect(remaining(s, T0 + 5 * MIN)).toBe(20 * MIN);
    s = pause(s, T0 + 5 * MIN);
    expect(remaining(s, T0 + 50 * MIN)).toBe(20 * MIN);
    s = resume(s, T0 + 50 * MIN);
    expect(remaining(s, T0 + 60 * MIN)).toBe(10 * MIN);
  });

  it("moves to break when work ends, then back to idle", () => {
    const s = startWork(IDLE, T0, 25, 5);
    const r = tick(s, T0 + 25 * MIN, false);
    expect(r.event).toBe("work_done");
    expect(r.state.phase).toBe("break");
    const r2 = tick(r.state, T0 + 30 * MIN, false);
    expect(r2.event).toBe("break_done");
    expect(r2.state.phase).toBe("idle");
  });

  it("never interrupts typing: waits, then switches after 60 s", () => {
    const s = startWork(IDLE, T0, 25, 5);
    const end = T0 + 25 * MIN;
    const a = tick(s, end, true);
    expect(a.event).toBeNull();
    expect(a.state.finishSince).toBe(end);
    const b = tick(a.state, end + 30_000, true);
    expect(b.event).toBeNull();
    const c = tick(b.state, end + FINISH_GRACE_MS, true);
    expect(c.event).toBe("work_done");
    // stops typing earlier → switches right away
    const d = tick(a.state, end + 5_000, false);
    expect(d.event).toBe("work_done");
  });

  it("survives a refresh: state is plain data", () => {
    const s = startWork(IDLE, T0);
    const restored = JSON.parse(JSON.stringify(s));
    expect(remaining(restored, T0 + MIN)).toBe(24 * MIN);
  });

  it("formats mm:ss", () => {
    expect(fmt(18 * MIN + 42_000)).toBe("18:42");
    expect(fmt(0)).toBe("00:00");
  });
});
