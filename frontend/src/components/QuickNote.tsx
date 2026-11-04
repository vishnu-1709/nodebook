import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { errorMessage } from "../api/client";
import { qk } from "../api/hooks";
import { lk } from "../api/lectures";
import { useCapture } from "../api/notes";
import type { CourseDetail, MapDoc } from "../api/types";
import { useUi } from "../app/store";
import { Modal } from "./Modal";

/** N from anywhere: saved to node > lecture > course; outside a course → inbox. */
export function QuickNote({ onClose }: { onClose: () => void }) {
  const ctx = useUi((s) => s.context);
  const showToast = useUi((s) => s.showToast);
  const qc = useQueryClient();
  const capture = useCapture();
  const [text, setText] = useState("");

  const course = ctx.courseId ? qc.getQueryData<CourseDetail>(qk.course(ctx.courseId)) : undefined;
  const lecture = course?.lectures.find((l) => l.id === ctx.lectureId);
  const map = ctx.courseId && ctx.lectureId ? qc.getQueryData<MapDoc>(lk.map(ctx.courseId, ctx.lectureId)) : undefined;
  const node = ctx.nodeId ? map?.nodes[ctx.nodeId] : undefined;
  const where = node?.label ?? lecture?.title ?? course?.course.name ?? "Notes inbox";

  const save = () => {
    if (!text.trim()) return;
    capture.mutate(
      { text, course_id: ctx.courseId, lecture_id: ctx.lectureId, node_id: ctx.nodeId },
      {
        onSuccess: () => {
          onClose();
          showToast(`Note saved to ${where}`);
        },
      },
    );
  };

  return (
    <Modal title="Quick note" onClose={onClose}>
      <p className="small muted">Saving to: <strong>{where}</strong></p>
      <label className="visually-hidden" htmlFor="quick-note">Note</label>
      <textarea
        id="quick-note"
        className="textarea"
        rows={4}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && (e.metaKey || e.ctrlKey || !e.shiftKey)) {
            e.preventDefault();
            save();
          }
        }}
        placeholder="Type and press Enter. Shift+Enter for a new line."
      />
      {capture.isError && <p className="banner banner-error">{errorMessage(capture.error)}</p>}
      <div className="row">
        <span className="spacer" />
        <button className="btn" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" onClick={save} disabled={!text.trim() || capture.isPending}>Save</button>
      </div>
    </Modal>
  );
}
