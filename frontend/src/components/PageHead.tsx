import type { ReactNode } from "react";
import { PomodoroChip } from "./PomodoroChip";

/** Page header for shell screens without a header bar (Today, Course, Settings…). */
export function PageHead({ kicker, title, actions }: { kicker?: ReactNode; title: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-head">
      <div className="grow">
        {kicker && <p className="date">{kicker}</p>}
        {typeof title === "string" ? <h1>{title}</h1> : title}
      </div>
      <div className="row wrap page-actions">
        {actions}
        <PomodoroChip />
      </div>
    </div>
  );
}
