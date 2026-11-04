import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useCourse, useCourses } from "../api/hooks";
import { minutesFor, useDueCounts } from "../api/review";
import { PageHead } from "../components/PageHead";

/** Review hub: due counts per course, lecture filter, Start review, Anki export. */
export function ReviewScreen() {
  const courses = useCourses();
  const counts = useDueCounts();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const total = counts.data?.total ?? 0;
  const only = params.get("course");
  const list = (courses.data ?? []).filter((c) => !only || c.id === only);
  return (
    <div className="content content-narrow">
      <PageHead
        title="Review"
        actions={<button className="btn btn-dark" disabled={!total} onClick={() => nav("/review/session")}>Start review · {total}</button>}
      />
      <p className="text-2 section">Cards and saved questions come back when you're about to forget them. Rate each one honestly: Again · Hard · Good · Easy.</p>
      <div className="stack">
        {list.map((c) => <CourseReview key={c.id} courseId={c.id} due={counts.data?.by_course[c.id] ?? 0} />)}
        {courses.data?.length === 0 && <p className="muted">Add a course first.</p>}
      </div>
    </div>
  );
}

function CourseReview({ courseId, due }: { courseId: string; due: number }) {
  const q = useCourse(courseId);
  const nav = useNavigate();
  const [lecture, setLecture] = useState("");
  if (!q.data) return null;
  return (
    <section className="card review-course">
      <div className="grow stack-tight">
        <h2>{q.data.course.name}</h2>
        <p className="small text-2"><span className="mono">{due}</span> due{due ? ` · about ${minutesFor(due)} min` : ""}</p>
      </div>
      <select className="select select-sm" aria-label="Lecture filter" value={lecture} onChange={(e) => setLecture(e.target.value)}>
        <option value="">All lectures</option>
        {q.data.lectures.map((l) => <option key={l.id} value={l.id}>{l.title}</option>)}
      </select>
      <a className="btn btn-sm" href={`/api/courses/${courseId}/anki${lecture ? `?lecture_id=${lecture}` : ""}`} download>Export to Anki</a>
      <button className="btn btn-dark btn-sm" disabled={!due} onClick={() => nav(`/review/session?course=${courseId}${lecture ? `&lecture=${lecture}` : ""}`)}>Start review</button>
    </section>
  );
}
