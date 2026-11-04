import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorMessage } from "../api/client";
import { qk, useCourse, useDeleteCourse, useRenameCourse } from "../api/hooks";
import { useGenerateMap, useReorderLectures, useUploadLecture } from "../api/lectures";
import { useNoteMutations } from "../api/notes";
import type { Lecture, Note, PracticeItem, StatusCounts } from "../api/types";
import { useUi } from "../app/store";
import { DropZone } from "../components/DropZone";
import { JobProgress } from "../components/JobProgress";
import { PageHead } from "../components/PageHead";
import { SourcesShelf } from "../components/SourcesShelf";
import { StatusBar, StatusLegend } from "../components/StatusBar";

type Tab = "lectures" | "sources" | "saved" | "notes";

export function CourseScreen() {
  const { courseId = "" } = useParams();
  const q = useCourse(courseId);
  const rename = useRenameCourse(courseId);
  const del = useDeleteCourse();
  const uploadLecture = useUploadLecture(courseId);
  const nav = useNavigate();
  const qc = useQueryClient();
  const setContext = useUi((s) => s.setContext);
  const open = useUi((s) => s.open);
  const [tab, setTab] = useState<Tab>("lectures");
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [uploadErr, setUploadErr] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);

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
  const { course, lectures, progress } = q.data!;

  const save = () => {
    if (name.trim() && name.trim() !== course.name) rename.mutate(name.trim());
    setEditing(false);
  };
  const onFiles = (files: File[]) => {
    setUploadErr("");
    for (const f of files) {
      if (!/\.(pdf|pptx)$/i.test(f.name)) {
        setUploadErr(`${f.name}: lectures need a PDF or PPTX file. Other files go in Sources.`);
        continue;
      }
      uploadLecture.mutate(f, { onError: (e) => setUploadErr(errorMessage(e)) });
    }
  };

  const title = editing ? (
    <input className="input title-input" value={name} autoFocus aria-label="Course name"
      onChange={(e) => setName(e.target.value)} onBlur={save}
      onKeyDown={(e) => { if (e.key === "Enter") save(); if (e.key === "Escape") setEditing(false); }} />
  ) : (
    <h1 onDoubleClick={() => { setName(course.name); setEditing(true); }}>{course.name}</h1>
  );

  return (
    <div className="content content-narrow">
      <PageHead
        title={title}
        actions={
          <>
            <button className="btn" onClick={() => open("generate")}>Generate <span className="kbd">G</span></button>
            <button className="btn btn-primary" onClick={() => fileInput.current?.click()}>+ Add lecture</button>
            <input ref={fileInput} type="file" accept=".pdf,.pptx" multiple className="visually-hidden" tabIndex={-1} aria-hidden="true"
              onChange={(e) => { const f = Array.from(e.target.files ?? []); e.target.value = ""; if (f.length) onFiles(f); }} />
          </>
        }
      />
      <div className="tabs" role="tablist" aria-label="Course sections">
        {(["lectures", "sources", "saved", "notes"] as Tab[]).map((t) => (
          <button key={t} role="tab" className="tab" aria-selected={tab === t} onClick={() => setTab(t)}>
            {t[0]!.toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>
      <div className="tab-panel">
        {tab === "lectures" && <CourseProgress progress={progress} />}
        {tab === "lectures" && (
          <section className="card stack lectures-card">
            <div className="card-head"><h2 className="grow">Lectures</h2>{lectures.length > 0 && <StatusLegend />}</div>
            {lectures.length > 0 && (
              <div className="lecture-rows">
                {lectures.map((l, i) => (
                  <LectureRow key={l.id} lecture={l} courseId={courseId} counts={progress[l.id]} first={i === 0} last={i === lectures.length - 1} all={lectures} />
                ))}
              </div>
            )}
            <DropZone accept=".pdf,.pptx" onFiles={onFiles} label="Choose slides" disabled={uploadLecture.isPending}>
              <span className="text-2">{lectures.length ? "+ Add lecture (drop PPT / PDF)" : "Drop a PPTX or PDF here to add your first lecture"}</span>
            </DropZone>
            {uploadLecture.isPending && <p className="muted small">Uploading…</p>}
            {uploadErr && <p className="banner banner-error">{uploadErr}</p>}
          </section>
        )}
        {tab === "sources" && <section className="card"><SourcesShelf courseId={courseId} lectures={lectures} /></section>}
        {tab === "saved" && <SavedView courseId={courseId} lectures={lectures} />}
        {tab === "notes" && <CourseNotes courseId={courseId} />}
      </div>
      <div className="row course-danger">
        <button className="btn btn-sm" onClick={() => { setName(course.name); setEditing(true); }}>Rename course</button>
        <button className="btn btn-sm btn-danger" onClick={() => {
          if (window.confirm(`Delete “${course.name}” and everything in it? This can't be undone.`)) del.mutate(course.id, { onSuccess: () => nav("/") });
        }}>Delete course</button>
      </div>
    </div>
  );
}

/** Course progress overview (SPEC §5.14): totals from the (performance-based) node statuses. */
function CourseProgress({ progress }: { progress: Record<string, StatusCounts> }) {
  const t: StatusCounts = { got_it: 0, revising: 0, confused: 0, not_started: 0, total: 0 };
  for (const c of Object.values(progress)) {
    t.got_it += c.got_it; t.revising += c.revising; t.confused += c.confused; t.not_started += c.not_started; t.total += c.total;
  }
  if (!t.total) return null;
  const pct = Math.round((t.got_it / t.total) * 100);
  return (
    <section className="card stack progress-card" aria-label="Course progress">
      <div className="card-head">
        <h2 className="grow">Progress</h2>
        <span className="text-2"><span className="next-big progress-big">{pct}%</span> of topics you've got</span>
      </div>
      <StatusBar c={t} />
      <div className="legend">
        <span><i className="sb-got" />Got it <strong className="mono">{t.got_it}</strong></span>
        <span><i className="sb-revising" />Revising <strong className="mono">{t.revising}</strong></span>
        <span><i className="sb-confused" />Confused <strong className="mono">{t.confused}</strong></span>
        <span><i className="sb-none" />Not started <strong className="mono">{t.not_started}</strong></span>
      </div>
      <p className="xsmall muted">Statuses update from your Test me, recall and review results once a topic has 3 results. Setting one by hand keeps yours.</p>
    </section>
  );
}

function LectureRow({ lecture: l, courseId, counts, first, last, all }: {
  lecture: Lecture; courseId: string; counts: StatusCounts | undefined; first: boolean; last: boolean; all: Lecture[];
}) {
  const gen = useGenerateMap(courseId, l.id);
  const reorder = useReorderLectures(courseId);
  const move = (d: number) => {
    const order = all.map((x) => x.id);
    const i = order.indexOf(l.id);
    const j = i + d;
    if (j < 0 || j >= order.length) return;
    [order[i], order[j]] = [order[j]!, order[i]!];
    reorder.mutate(order);
  };
  const running = l.map_status === "queued" || l.map_status === "running";
  return (
    <div className="lecture-rowx">
      <Link to={`/course/${courseId}/lecture/${l.id}`} className="lecture-link">{l.title}</Link>
      <div>
        {running ? <JobProgress jobId={l.map_job_id} fallbackText="Generating map…" /> :
          l.map_status === "failed" ? (
            <span className="row small"><span className="error-text">Map failed: {l.map_error}</span><button className="btn btn-sm" onClick={() => gen.mutate()}>Retry</button></span>
          ) : <StatusBar c={counts} />}
      </div>
      <span className="count">{counts && counts.total > 0 ? `${counts.total} nodes` : running ? "" : "new"}</span>
      <span className="row">
        <button className="btn btn-ghost btn-sm" disabled={first} onClick={() => move(-1)} aria-label={`Move ${l.title} up`}>↑</button>
        <button className="btn btn-ghost btn-sm" disabled={last} onClick={() => move(1)} aria-label={`Move ${l.title} down`}>↓</button>
      </span>
    </div>
  );
}

interface SavedOut {
  practice: { item: PracticeItem; lecture_id: string | null; lecture_title: string; node_label: string }[];
  notes: { note: Note; lecture_id: string | null; lecture_title: string; node_label: string }[];
}

function SavedView({ courseId, lectures }: { courseId: string; lectures: Lecture[] }) {
  const q = useQuery({ queryKey: ["saved", courseId], queryFn: () => api<SavedOut>(`/courses/${courseId}/saved`) });
  const [type, setType] = useState<"all" | "question" | "card" | "note">("all");
  const [lec, setLec] = useState("all");
  const rows = [
    ...(q.data?.practice ?? []).map((p) => ({ id: p.item.id, kind: p.item.type, text: p.item.front, sub: p.item.back, lecture_id: p.lecture_id, where: [p.lecture_title, p.node_label].filter(Boolean).join(" › "), unverified: p.item.answer_status === "ai_unverified" && p.item.type === "question" })),
    ...(q.data?.notes ?? []).map((n) => ({ id: n.note.id, kind: "note" as const, text: n.note.text, sub: "", lecture_id: n.lecture_id, where: [n.lecture_title, n.node_label].filter(Boolean).join(" › "), unverified: false })),
  ].filter((r) => (type === "all" || r.kind === type) && (lec === "all" || (r.lecture_id ?? "course") === lec));
  return (
    <section className="card stack">
      <div className="row wrap">
        {(["all", "question", "card", "note"] as const).map((t) => (
          <button key={t} className="chip" aria-pressed={type === t} onClick={() => setType(t)}>
            {t === "all" ? "All" : t === "question" ? "Questions" : t === "card" ? "Flashcards" : "Notes"}
          </button>
        ))}
        <span className="spacer" />
        <select className="select select-sm" aria-label="Lecture" value={lec} onChange={(e) => setLec(e.target.value)}>
          <option value="all">All lectures</option>
          <option value="course">Course level</option>
          {lectures.map((l) => <option key={l.id} value={l.id}>{l.title}</option>)}
        </select>
      </div>
      {rows.length === 0 && <p className="muted">Nothing saved yet. Generate questions or keep answers from a topic's thread.</p>}
      <ul className="note-list">
        {rows.map((r) => (
          <li key={r.id} className="note">
            <p className="xsmall muted">{r.kind === "question" ? "Question" : r.kind === "card" ? "Flashcard" : "Note"} · {r.where}{r.unverified ? " · AI answer · check it" : ""}</p>
            <p className="note-text">{r.text}</p>
            {r.sub && <details><summary className="small muted">Answer</summary><p className="note-text">{r.sub}</p></details>}
          </li>
        ))}
      </ul>
    </section>
  );
}

function CourseNotes({ courseId }: { courseId: string }) {
  const q = useQuery({ queryKey: ["notes", courseId], queryFn: () => api<Note[]>(`/courses/${courseId}/notes`) });
  const m = useNoteMutations(courseId, null);
  const [text, setText] = useState("");
  return (
    <section className="card stack">
      <form className="row" onSubmit={(e) => { e.preventDefault(); if (text.trim()) m.add.mutate({ text }, { onSuccess: () => setText("") }); }}>
        <input className="input" aria-label="New course note" value={text} onChange={(e) => setText(e.target.value)} placeholder="A note for the whole course…" />
        <button className="btn btn-primary" disabled={!text.trim()}>Add</button>
      </form>
      {q.data?.length === 0 && <p className="muted">No course notes yet.</p>}
      <ul className="note-list">
        {q.data?.slice().reverse().map((n) => (
          <li key={n.id} className="note">
            <p className="note-text">{n.text}</p>
            <div className="row"><span className="xsmall muted">{new Date(n.created_at).toLocaleDateString()}</span><span className="spacer" />
              <button className="btn btn-ghost btn-sm" onClick={() => window.confirm("Delete this note?") && m.remove.mutate(n.id)}>Delete</button></div>
          </li>
        ))}
      </ul>
    </section>
  );
}
