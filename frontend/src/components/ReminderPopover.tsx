import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { errorMessage } from "../api/client";
import { qk } from "../api/hooks";
import { lk } from "../api/lectures";
import { parseReminder, useReminderMutations, type Parsed, type ReminderLink } from "../api/today";
import type { CourseDetail, MapDoc } from "../api/types";
import { useUi } from "../app/store";
import { Modal } from "./Modal";

function toLocalInput(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

/** R (UI.md §3.9): natural-language text → parsed date + #tags shown as chips → confirm. */
export function ReminderPopover({ onClose }: { onClose: () => void }) {
  const ctx = useUi((s) => s.context);
  const showToast = useUi((s) => s.showToast);
  const qc = useQueryClient();
  const m = useReminderMutations();
  const [text, setText] = useState("");
  const [parsed, setParsed] = useState<Parsed | null>(null);
  const [manualDue, setManualDue] = useState<string>("");
  const [linkOn, setLinkOn] = useState(Boolean(ctx.courseId));

  const course = ctx.courseId ? qc.getQueryData<CourseDetail>(qk.course(ctx.courseId)) : undefined;
  const map = ctx.courseId && ctx.lectureId ? qc.getQueryData<MapDoc>(lk.map(ctx.courseId, ctx.lectureId)) : undefined;
  const lecture = course?.lectures.find((l) => l.id === ctx.lectureId);
  const node = ctx.nodeId ? map?.nodes[ctx.nodeId] : undefined;
  const link: ReminderLink | null = ctx.courseId
    ? node ? { kind: "node", id: node.id, course_id: ctx.courseId, lecture_id: ctx.lectureId }
      : lecture ? { kind: "lecture", id: lecture.id, course_id: ctx.courseId, lecture_id: lecture.id }
      : { kind: "course", id: ctx.courseId, course_id: ctx.courseId, lecture_id: null }
    : null;
  const linkLabel = node?.label ?? lecture?.title ?? course?.course.name ?? "";

  useEffect(() => {
    if (!text.trim()) { setParsed(null); return; }
    const t = window.setTimeout(() => { parseReminder(text).then(setParsed).catch(() => setParsed(null)); }, 250);
    return () => window.clearTimeout(t);
  }, [text]);
  useEffect(() => { if (parsed?.due_at) setManualDue(toLocalInput(parsed.due_at)); }, [parsed?.due_at]);

  const due = manualDue ? new Date(manualDue).toISOString() : null;
  const save = () => {
    if (!parsed || !due) return;
    m.create.mutate(
      { text: parsed.text || text, due_at: due, tags: parsed.tags, link: linkOn ? link : null, course_id: linkOn ? ctx.courseId : null },
      { onSuccess: () => { onClose(); showToast("Reminder added"); } },
    );
  };

  return (
    <Modal title="Reminder" onClose={onClose} popover>
      <label className="visually-hidden" htmlFor="reminder-text">Reminder</label>
      <input id="reminder-text" className="input quick-input" value={text} onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); save(); } }}
        placeholder="e.g. lab exam 14 nov #exam" />
      <div className="row wrap">
        <label className="visually-hidden" htmlFor="reminder-due">Due</label>
        <input id="reminder-due" type="datetime-local" className={due ? "chip on date-chip" : "chip date-chip"} value={manualDue} onChange={(e) => setManualDue(e.target.value)} />
        {parsed?.tags.map((t) => <span key={t} className="chip on">#{t}</span>)}
        {link && (
          <button type="button" className="chip" aria-pressed={linkOn} onClick={() => setLinkOn(!linkOn)} title="Link this reminder">
            {linkOn ? "✓ " : ""}Link to {linkLabel}
          </button>
        )}
        <span className="spacer" />
        <span className="hint">Enter add · Esc close</span>
      </div>
      {text.trim() && parsed && !parsed.due_at && !manualDue && <p className="small muted">No date found — pick one above.</p>}
      {m.create.isError && <p className="banner banner-error small">{errorMessage(m.create.error)}</p>}
    </Modal>
  );
}
