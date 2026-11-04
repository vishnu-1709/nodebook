import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { errorMessage } from "../api/client";
import { useCourse, useDeleteCourse, useRenameCourse } from "../api/hooks";
import { useGenerateMap, useReorderLectures, useUploadLecture } from "../api/lectures";
import type { Lecture } from "../api/types";
import { useUi } from "../app/store";
import { DropZone } from "../components/DropZone";
import { JobProgress } from "../components/JobProgress";
import { SourcesShelf } from "../components/SourcesShelf";
import { useQueryClient } from "@tanstack/react-query";
import { qk } from "../api/hooks";

export function CourseScreen() {
  const { courseId = "" } = useParams();
  const q = useCourse(courseId);
  const rename = useRenameCourse(courseId);
  const del = useDeleteCourse();
  const uploadLecture = useUploadLecture(courseId);
  const reorder = useReorderLectures(courseId);
  const nav = useNavigate();
  const qc = useQueryClient();
  const setContext = useUi((s) => s.setContext);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [uploadErr, setUploadErr] = useState("");

  useEffect(() => {
    setContext({ courseId, lectureId: null, nodeId: null });
    return () => setContext({ courseId: null, lectureId: null, nodeId: null });
  }, [courseId, setContext]);

  const busy = q.data?.lectures.some((l) => l.map_status === "queued" || l.map_status === "running");
  useEffect(() => {
    if (!busy) return;
    const t = window.setInterval(() => void qc.invalidateQueries({ queryKey: qk.course(courseId) }), 1500);
    return () => window.clearInterval(t);
  }, [busy, courseId, qc]);

  if (q.isLoading) return <div className="content muted">Loading…</div>;
  if (q.isError) return <div className="content"><p className="banner banner-error">{errorMessage(q.error)}</p></div>;
  const { course, lectures } = q.data!;

  const save = () => {
    if (name.trim() && name.trim() !== course.name) rename.mutate(name.trim());
    setEditing(false);
  };

  const onFiles = (files: File[]) => {
    setUploadErr("");
    for (const f of files) {
      if (!/\.(pdf|pptx)$/i.test(f.name)) {
        setUploadErr(`${f.name}: lectures need a PDF or PPTX file. Other files go in Sources below.`);
        continue;
      }
      uploadLecture.mutate(f, { onError: (e) => setUploadErr(errorMessage(e)) });
    }
  };

  const move = (idx: number, delta: number) => {
    const order = lectures.map((l) => l.id);
    const j = idx + delta;
    if (j < 0 || j >= order.length) return;
    [order[idx], order[j]] = [order[j]!, order[idx]!];
    reorder.mutate(order);
  };

  return (
    <div className="content content-narrow">
      <div className="page-head">
        {editing ? (
          <input
            className="input title-input"
            value={name}
            autoFocus
            aria-label="Course name"
            onChange={(e) => setName(e.target.value)}
            onBlur={save}
            onKeyDown={(e) => {
              if (e.key === "Enter") save();
              if (e.key === "Escape") setEditing(false);
            }}
          />
        ) : (
          <h1>{course.name}</h1>
        )}
        <span className="spacer" />
        {!editing && (
          <button className="btn btn-sm" onClick={() => { setName(course.name); setEditing(true); }}>Rename</button>
        )}
        <button
          className="btn btn-sm btn-danger"
          onClick={() => {
            if (window.confirm(`Delete “${course.name}” and everything in it? This can't be undone.`)) {
              del.mutate(course.id, { onSuccess: () => nav("/") });
            }
          }}
        >
          Delete
        </button>
      </div>

      <section className="stack section">
        <h2>Lectures</h2>
        {lectures.length > 0 && (
          <ol className="list">
            {lectures.map((l, i) => (
              <LectureRow key={l.id} lecture={l} courseId={courseId} first={i === 0} last={i === lectures.length - 1}
                onMove={(d) => move(i, d)} />
            ))}
          </ol>
        )}
        <DropZone accept=".pdf,.pptx" onFiles={onFiles} label="Choose slides" disabled={uploadLecture.isPending}>
          <span className="muted">{lectures.length ? "Drop another deck to add a lecture" : "Drop a PPTX or PDF here to add your first lecture"}</span>
        </DropZone>
        {uploadLecture.isPending && <p className="muted small">Uploading…</p>}
        {uploadErr && <p className="banner banner-error">{uploadErr}</p>}
      </section>

      <SourcesShelf courseId={courseId} />
    </div>
  );
}

function LectureRow({ lecture: l, courseId, first, last, onMove }: {
  lecture: Lecture; courseId: string; first: boolean; last: boolean; onMove: (d: number) => void;
}) {
  const gen = useGenerateMap(courseId, l.id);
  return (
    <li className="list-row lecture-row">
      <div className="grow stack-tight">
        <Link to={`/course/${courseId}/lecture/${l.id}`} className="lecture-link">{l.title}</Link>
        {(l.map_status === "queued" || l.map_status === "running") && <JobProgress jobId={l.map_job_id} fallbackText="Generating map…" />}
        {l.map_status === "failed" && (
          <div className="row small">
            <span className="error-text">Map failed: {l.map_error}</span>
            <button className="btn btn-sm" onClick={() => gen.mutate()}>Retry</button>
          </div>
        )}
        {l.map_status === "ready" && l.uncovered_slides.length > 0 && (
          <span className="small muted">{l.uncovered_slides.length} slides not in the map</span>
        )}
      </div>
      <button className="btn btn-ghost btn-sm" disabled={first} onClick={() => onMove(-1)} aria-label={`Move ${l.title} up`}>↑</button>
      <button className="btn btn-ghost btn-sm" disabled={last} onClick={() => onMove(1)} aria-label={`Move ${l.title} down`}>↓</button>
    </li>
  );
}
