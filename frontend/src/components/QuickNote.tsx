import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { errorMessage } from "../api/client";
import { qk } from "../api/hooks";
import { lk } from "../api/lectures";
import { useCapture, useDestinations, type NoteDestination } from "../api/notes";
import type { CourseDetail, MapDoc } from "../api/types";
import { useUi } from "../app/store";
import { Modal } from "./Modal";

/** N from anywhere (UI.md §3.9): saved to node > lecture > course; outside a course → inbox. */
export function QuickNote({ onClose }: { onClose: () => void }) {
  const ctx = useUi((s) => s.context);
  const showToast = useUi((s) => s.showToast);
  const qc = useQueryClient();
  const capture = useCapture();
  const [text, setText] = useState("");
  const [changing, setChanging] = useState(false);
  const dests = useDestinations(changing);

  const course = ctx.courseId ? qc.getQueryData<CourseDetail>(qk.course(ctx.courseId)) : undefined;
  const lecture = course?.lectures.find((l) => l.id === ctx.lectureId);
  const map = ctx.courseId && ctx.lectureId ? qc.getQueryData<MapDoc>(lk.map(ctx.courseId, ctx.lectureId)) : undefined;
  const node = ctx.nodeId ? map?.nodes[ctx.nodeId] : undefined;
  const ctxLabel = [lecture?.title, node?.label].filter(Boolean).join(" › ") || course?.course.name || "Notes inbox";
  const [dest, setDest] = useState<NoteDestination>({
    course_id: ctx.courseId, lecture_id: ctx.lectureId, node_id: ctx.nodeId, label: ctxLabel,
  });

  const save = () => {
    if (!text.trim()) return;
    capture.mutate(
      { text, course_id: dest.course_id, lecture_id: dest.lecture_id, node_id: dest.node_id },
      { onSuccess: () => { onClose(); showToast("Saved"); } },
    );
  };

  return (
    <Modal title="Quick note" onClose={onClose} popover>
      <label className="visually-hidden" htmlFor="quick-note">Quick note</label>
      <textarea
        id="quick-note"
        className="input quick-input"
        rows={Math.min(3, Math.max(1, text.split("\n").length, Math.ceil(text.length / 60)))}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); save(); } }}
        placeholder="Quick note…"
      />
      <div className="row wrap">
        {changing ? (
          <select className="select select-sm" aria-label="Save to" autoFocus value=""
            onChange={(e) => {
              const v = e.target.value;
              if (v === "inbox") setDest({ course_id: null, lecture_id: null, node_id: null, label: "Notes inbox" });
              else { const d = dests.data?.[Number(v)]; if (d) setDest(d); }
              setChanging(false);
            }}>
            <option value="" disabled>{dests.isLoading ? "Loading…" : "Save to…"}</option>
            <option value="inbox">Notes inbox</option>
            {dests.data?.map((d, i) => <option key={i} value={i}>{d.label}</option>)}
          </select>
        ) : (
          <button className="chip on" onClick={() => setChanging(true)} title="Change where this note goes">→ {dest.label}</button>
        )}
        <span className="spacer" />
        <span className="hint">Enter save · Esc close</span>
      </div>
      {capture.isError && <p className="banner banner-error small">{errorMessage(capture.error)}</p>}
    </Modal>
  );
}
