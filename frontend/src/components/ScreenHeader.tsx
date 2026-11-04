import type { ReactNode } from "react";
import { PomodoroChip } from "./PomodoroChip";

/** Header bar used by every shell screen (UI.md §2): pomodoro chip always top-right. */
export function ScreenHeader({ children, right, plain }: { children?: ReactNode; right?: ReactNode; plain?: boolean }) {
  return (
    <header className={plain ? "screen-head plain" : "screen-head"}>
      {children}
      <span className="spacer" />
      {right}
      <PomodoroChip />
    </header>
  );
}
