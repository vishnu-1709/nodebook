import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useCourse, useDeleteCourse, useRenameCourse } from "../api/hooks";
import { errorMessage } from "../api/client";
import { useUi } from "../app/store";

export function CourseScreen() {
  const { courseId = "" } = useParams();
  const q = useCourse(courseId);
  const rename = useRenameCourse(courseId);
  const del = useDeleteCourse();
  const nav = useNavigate();
  const setContext = useUi((s) => s.setContext);
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");

  useEffect(() => {
    setContext({ courseId, lectureId: null, nodeId: null });
    return () => setContext({ courseId: null, lectureId: null, nodeId: null });
  }, [courseId, setContext]);

  if (q.isLoading) return <div className="content muted">Loading…</div>;
  if (q.isError) return <div className="content"><p className="banner banner-error">{errorMessage(q.error)}</p></div>;
  const { course, lectures } = q.data!;

  const save = () => {
    if (name.trim() && name.trim() !== course.name) rename.mutate(name.trim());
    setEditing(false);
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
      <section className="stack">
        <h2>Lectures</h2>
        {lectures.length === 0 && <p className="muted">No lectures yet. Drop a PPTX or PDF here to add one.</p>}
      </section>
    </div>
  );
}
