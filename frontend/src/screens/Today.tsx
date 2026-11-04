import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { errorMessage } from "../api/client";
import { useCourse, useCourses } from "../api/hooks";
import { useUploadLecture } from "../api/lectures";
import { BUILTIN_TAG_COLOUR, relativeDue, useReminderMutations, useReminders, useToday, type Reminder } from "../api/today";
import { minutesFor, useDueCounts } from "../api/review";
import { useUi } from "../app/store";
import { DropZone } from "../components/DropZone";
import { PageHead } from "../components/PageHead";
import { StatusBar, StatusLegend } from "../components/StatusBar";

function todayLabel(): string {
  return new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });
}

export function Today() {
  const today = useToday();
  const courses = useCourses();
  const open = useUi((s) => s.open);
  const nav = useNavigate();
  const t = today.data;
  const empty = t && !t.has_courses;

  return (
    <div className="content content-narrow">
      <PageHead
        kicker={todayLabel()}
        title="Today"
        actions={
          <>
            <button className="btn" onClick={() => open("quick_note")}>+ Quick note <span className="kbd">N</span></button>
            <button className="btn btn-primary" onClick={() => open("generate")}>Generate <span className="kbd">G</span></button>
          </>
        }
      />
      {today.isError && <p className="banner banner-error">{errorMessage(today.error)}</p>}
      {empty && (
        <div className="card stack empty-state">
          <h2>Start with a course</h2>
          <p className="text-2">Create a course, then drop in lecture slides to get a mind map you can study from.</p>
          <div><button className="btn btn-primary" onClick={() => open("new_course")}>Add your first course</button></div>
        </div>
      )}
      {t && !empty && (
        <div className="stack today">
          <div className="next-cards">
            <DueCard />
            <section className="card next-card" aria-label="Weak topics">
              <p className="next-kicker">Weak topics</p>
              {t.weak_nodes.length === 0 ? (
                <>
                  <p className="next-big">0</p>
                  <p className="small text-2">Nothing marked confused. Pick a topic and press Test me.</p>
                </>
              ) : (
                <>
                  <p><span className="next-big">{t.weak_nodes.length}</span> <span className="text-2">topic{t.weak_nodes.length > 1 ? "s" : ""} still confused</span></p>
                  <ul className="weak-list">
                    {t.weak_nodes.slice(0, 3).map((w) => (
                      <li key={w.node_id}>
                        <Link to={`/course/${w.course_id}/lecture/${w.lecture_id}?node=${w.node_id}`}>{w.label}</Link>
                        <span className="small muted"> · {w.lecture_title}</span>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </section>
            <section className="card next-card" aria-label="Next exam">
              <p className="next-kicker">Next exam</p>
              {t.exam ? (
                <>
                  <p><span className="next-big">{t.exam.days}</span> <span className="text-2">day{t.exam.days === 1 ? "" : "s"} · {t.exam.reminder.text}{courseName(courses.data, t.exam.reminder.course_id)}</span></p>
                  {examWeak(t) > 0 && <p className="confused-text small">{examWeak(t)} topic{examWeak(t) > 1 ? "s" : ""} still confused</p>}
                </>
              ) : (
                <>
                  <p className="small text-2">No exam yet. Add a reminder tagged #exam to start a countdown.</p>
                  <div><button className="btn btn-sm" onClick={() => open("reminder")}>+ Reminder <span className="kbd">R</span></button></div>
                </>
              )}
            </section>
          </div>

          <RemindersCard />

          {t.current_course_id && <LecturesCard courseId={t.current_course_id} onOpen={(id) => nav(`/course/${t.current_course_id}/lecture/${id}`)} />}
        </div>
      )}
    </div>
  );
}

function DueCard() {
  const counts = useDueCounts();
  const nav = useNavigate();
  const n = counts.data?.total ?? 0;
  return (
    <section className="card next-card" aria-label="Due for review">
      <p className="next-kicker">Due for review</p>
      <p><span className="next-big">{n}</span> <span className="text-2">{n === 1 ? "item" : "cards"} · about {minutesFor(n)} min</span></p>
      <div><button className="btn btn-dark" disabled={!n} onClick={() => nav("/review/session")}>Start review</button></div>
    </section>
  );
}

function courseName(list: { id: string; name: string }[] | undefined, id: string | null): string {
  const c = list?.find((x) => x.id === id);
  return c ? `, ${c.name}` : "";
}

function examWeak(t: NonNullable<ReturnType<typeof useToday>["data"]>): number {
  const cid = t.exam?.reminder.course_id;
  return cid ? t.weak_nodes.filter((w) => w.course_id === cid).length : t.weak_nodes.length;
}

function RemindersCard() {
  const today = useToday();
  const rem = useReminders();
  const m = useReminderMutations();
  const open = useUi((s) => s.open);
  const [tag, setTag] = useState<string | null>(null);
  const t = today.data;
  if (!t) return null;
  const rows: { r: Reminder; when: "overdue" | "today" | "week" }[] = [
    ...t.overdue.map((r) => ({ r, when: "overdue" as const })),
    ...t.today.map((r) => ({ r, when: "today" as const })),
    ...t.upcoming.map((r) => ({ r, when: "week" as const })),
  ].filter((x) => !tag || x.r.tags.includes(tag));
  const tagsInUse = Array.from(new Set([...t.overdue, ...t.today, ...t.upcoming].flatMap((r) => r.tags)));
  const colour = (name: string) => BUILTIN_TAG_COLOUR[name] ?? rem.data?.custom_tags.find((c) => c.name === name)?.colour ?? "tag-6";

  return (
    <section className="card" aria-label="Upcoming reminders">
      <div className="card-head">
        <h2 className="grow">Upcoming</h2>
        {tagsInUse.length > 0 && (
          <div className="chips">
            <button className="chip" aria-pressed={tag === null} onClick={() => setTag(null)}>All</button>
            {tagsInUse.map((x) => <button key={x} className="chip" aria-pressed={tag === x} onClick={() => setTag(tag === x ? null : x)}>#{x}</button>)}
          </div>
        )}
        <button className="btn btn-sm" onClick={() => open("reminder")}>+ Reminder <span className="kbd">R</span></button>
      </div>
      {rows.length === 0 ? (
        <p className="small text-2">Nothing in the next 7 days.</p>
      ) : (
        <ul className="list reminder-list">
          {rows.map(({ r, when }) => (
            <li key={r.id} className="list-row reminder-row">
              <input type="checkbox" aria-label={`Done: ${r.text}`} checked={r.done} onChange={() => m.patch.mutate({ id: r.id, done: true })} />
              {r.tags.map((x) => <span key={x} className={`tag-chip ${colour(x)}`}>{x}</span>)}
              <span className="grow">
                {r.link ? <Link to={linkHref(r)} className="lecture-link">{r.text}</Link> : r.text}
              </span>
              <span className={when === "overdue" ? "small confused-text" : "small text-2"}>{relativeDue(r.due_at)}</span>
              <button className="btn btn-ghost btn-sm" aria-label={`Delete ${r.text}`} onClick={() => m.remove.mutate(r.id)}>✕</button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function linkHref(r: Reminder): string {
  const l = r.link!;
  if (l.kind === "course") return `/course/${l.id}`;
  if (l.kind === "lecture") return `/course/${l.course_id}/lecture/${l.id}`;
  return `/course/${l.course_id}/lecture/${l.lecture_id}?node=${l.id}`;
}

function LecturesCard({ courseId, onOpen }: { courseId: string; onOpen: (lectureId: string) => void }) {
  const q = useCourse(courseId);
  const upload = useUploadLecture(courseId);
  const [err, setErr] = useState("");
  if (!q.data) return null;
  const { course, lectures, progress } = q.data;
  return (
    <section className="card" aria-label={`${course.name} lectures`}>
      <div className="card-head">
        <h2 className="grow">{course.name} · lectures</h2>
        <StatusLegend />
      </div>
      <div className="lecture-rows">
        {lectures.map((l) => (
          <div key={l.id} className="lecture-rowx today-row">
            <button className="link-reset lecture-link" onClick={() => onOpen(l.id)}>{l.title}</button>
            <StatusBar c={progress[l.id]} />
            <span className="count">{progress[l.id]?.total ? `${progress[l.id]!.total} nodes` : "new"}</span>
          </div>
        ))}
      </div>
      <DropZone accept=".pdf,.pptx" label="Choose slides" onFiles={(fs) => {
        setErr("");
        fs.forEach((f) => upload.mutate(f, { onError: (e) => setErr(errorMessage(e)) }));
      }}>
        <span className="text-2">+ Add lecture (drop PPT / PDF)</span>
      </DropZone>
      {err && <p className="banner banner-error small">{err}</p>}
    </section>
  );
}
