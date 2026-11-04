import { useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { errorMessage } from "../api/client";
import { useGenDestinations, useGenerate, type Chip, type GenType, type GeneratedItem } from "../api/generate";
import { useCourse, useCourses } from "../api/hooks";
import { lk, useSources, useUploadSource } from "../api/lectures";
import type { GradeResult } from "../api/testme";
import type { MapDoc } from "../api/types";
import { isTypingTarget } from "../app/shortcuts";
import { useUi } from "../app/store";
import { useModalLayer } from "./Modal";
import { PomodoroChip } from "./PomodoroChip";

const TYPES: { id: GenType; label: string; noun: string }[] = [
  { id: "questions", label: "Practice questions", noun: "Question" },
  { id: "flashcards", label: "Flashcards", noun: "Flashcard" },
  { id: "summary", label: "Summary", noun: "Summary" },
  { id: "explain", label: "Explain a topic", noun: "Explanation" },
];
const CHIPS: { id: Chip; label: string }[] = [
  { id: "harder", label: "Harder" },
  { id: "easier", label: "Easier" },
  { id: "conceptual", label: "Conceptual" },
  { id: "numerical", label: "Numerical" },
];
const VERDICT: Record<GradeResult["verdict"], string> = { correct: "Correct", partly: "Partly", wrong: "Not quite" };

/** Generate — full screen (UI.md §3.5). */
export function GeneratePanel({ onClose }: { onClose: () => void }) {
  useModalLayer(onClose);
  const ctx = useUi((s) => s.context);
  const showToast = useUi((s) => s.showToast);
  const courses = useCourses();
  const [courseId, setCourseId] = useState<string | null>(ctx.courseId);
  useEffect(() => {
    if (!courseId && courses.data?.length === 1) setCourseId(courses.data[0]!.id);
  }, [courseId, courses.data]);

  const course = useCourse(courseId ?? undefined);
  const sources = useSources(courseId ?? "");
  const upload = useUploadSource(courseId ?? "");
  const dests = useGenDestinations(courseId);
  const gen = useGenerate(courseId ?? "");
  const qc = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);

  const [lectureIds, setLectureIds] = useState<string[]>(ctx.lectureId ? [ctx.lectureId] : []);
  const [sourceIds, setSourceIds] = useState<string[]>([]);
  const [type, setType] = useState<GenType>("questions");
  const [steer, setSteer] = useState("");
  const [chips, setChips] = useState<Chip[]>([]);
  const ctxMap = ctx.courseId && ctx.lectureId ? qc.getQueryData<MapDoc>(lk.map(ctx.courseId, ctx.lectureId)) : undefined;
  const [topic, setTopic] = useState(ctx.nodeId ? ctxMap?.nodes[ctx.nodeId]?.label ?? "" : "");

  const [item, setItem] = useState<GeneratedItem | null>(null);
  const [count, setCount] = useState(0);
  const [savedCount, setSavedCount] = useState(0);
  const [seen, setSeen] = useState<string[]>([]);
  const [answer, setAnswer] = useState("");
  const [grade, setGrade] = useState<GradeResult | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [destIdx, setDestIdx] = useState<number>(0);

  const shelf = useMemo(() => (sources.data ?? []).filter((s) => !s.lecture_id), [sources.data]);
  const canGenerate = Boolean(courseId) && (lectureIds.length > 0 || sourceIds.length > 0) && (type !== "explain" || topic.trim().length > 0);

  const run = (exclude: string[]) => {
    if (!canGenerate) return;
    setGrade(null);
    setAnswer("");
    setRevealed(false);
    gen.generate.mutate(
      { type, source_ids: sourceIds, lecture_ids: lectureIds, steer, chips, topic, exclude },
      {
        onSuccess: (it) => {
          setItem(it);
          setCount((c) => c + 1);
          setSeen((s) => [...s, it.key]);
          const list = dests.data ?? [];
          const i = list.findIndex((d) => it.suggested && d.node_id === it.suggested.node_id && d.lecture_id === it.suggested.lecture_id);
          setDestIdx(i >= 0 ? i : 0);
        },
      },
    );
  };
  const next = () => run(seen);
  const discard = () => { setItem(null); setGrade(null); };
  const save = () => {
    if (!item || !courseId) return;
    const d = dests.data?.[destIdx] ?? { course_id: courseId, lecture_id: null, node_id: null, label: "Course (unassigned)" };
    gen.save.mutate({ item, destination: d }, {
      onSuccess: () => { setSavedCount((n) => n + 1); showToast(`Saved to ${d.label}`); next(); },
    });
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!item || isTypingTarget(e.target) || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.key === "d" || e.key === "D") { e.preventDefault(); discard(); }
      else if (e.key === "ArrowRight") { e.preventDefault(); next(); }
      else if (e.key === "s" || e.key === "S") { e.preventDefault(); save(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  const toggle = <T,>(list: T[], v: T, set: (x: T[]) => void) => set(list.includes(v) ? list.filter((x) => x !== v) : [...list, v]);
  const isQA = item && (item.type === "questions" || item.type === "flashcards");
  const noun = TYPES.find((t) => t.id === (item?.type ?? type))!.noun;
  const destLabel = dests.data?.[destIdx]?.label ?? "Course (unassigned)";

  return (
    <div className="fullscreen gen-screen" role="dialog" aria-modal="true" aria-label="Generate">
      <header className="screen-head">
        <button className="btn btn-ghost btn-sm" onClick={onClose}>← Back</button>
        <span className="screen-title">Generate · {course.data?.course.name ?? "choose a course"}</span>
        <span className="spacer" />
        <span className="small muted">Saved this session: <strong className="mono">{savedCount}</strong></span>
        <PomodoroChip />
      </header>
      <div className="gen-body">
        <aside className="gen-left stack">
          {!ctx.courseId && (
            <label className="field">
              <span>Course</span>
              <select className="select" value={courseId ?? ""} onChange={(e) => { setCourseId(e.target.value); setLectureIds([]); setSourceIds([]); setItem(null); }}>
                <option value="" disabled>Choose a course…</option>
                {courses.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
              </select>
            </label>
          )}
          <div className="gen-step">
            <h3>1 · Use these sources</h3>
            <div className="chips">
              {course.data?.lectures.map((l) => (
                <button key={l.id} type="button" className="chip filled" aria-pressed={lectureIds.includes(l.id)} onClick={() => toggle(lectureIds, l.id, setLectureIds)}>
                  {lectureIds.includes(l.id) ? "✓ " : ""}{l.title}
                </button>
              ))}
              {shelf.map((s) => (
                <button key={s.id} type="button" className="chip filled" aria-pressed={sourceIds.includes(s.id)} onClick={() => toggle(sourceIds, s.id, setSourceIds)}>
                  {sourceIds.includes(s.id) ? "✓ " : ""}{s.filename.replace(/\.[a-z0-9]+$/i, "")}
                </button>
              ))}
              {courseId && (
                <button type="button" className="chip chip-dashed" onClick={() => fileInput.current?.click()} disabled={upload.isPending}>
                  {upload.isPending ? "Uploading…" : "+ Upload"}
                </button>
              )}
              <input ref={fileInput} type="file" accept=".pdf,.pptx,.txt,.md" className="visually-hidden" tabIndex={-1} aria-hidden="true"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  e.target.value = "";
                  if (f) upload.mutate({ file: f, kind: /pyq|paper|exam|midsem|endsem/i.test(f.name) ? "pyq" : "other" }, { onSuccess: (m) => setSourceIds((ids) => [...ids, m.id]) });
                }} />
            </div>
          </div>
          <div className="gen-step">
            <h3>2 · Make</h3>
            <div className="make-grid" role="radiogroup" aria-label="Make">
              {TYPES.map((t) => (
                <button key={t.id} type="button" role="radio" aria-checked={type === t.id} className="make-card" onClick={() => setType(t.id)}>{t.label}</button>
              ))}
            </div>
            {type === "explain" && (
              <input className="input" aria-label="Topic to explain" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="Topic, e.g. Ridge regression" />
            )}
          </div>
          <div className="gen-step">
            <h3>3 · Steer (optional)</h3>
            <input className="input" aria-label="Steer" value={steer} onChange={(e) => setSteer(e.target.value)} placeholder="e.g. PYQ style, more numericals" />
            <div className="chips">
              {CHIPS.map((c) => (
                <button key={c.id} type="button" className="chip" aria-pressed={chips.includes(c.id)} onClick={() => toggle(chips, c.id, setChips)}>{c.label}</button>
              ))}
            </div>
          </div>
        </aside>

        <section className="gen-right">
          {!item ? (
            <div className="gen-card gen-empty stack">
              <p className="text-2">{canGenerate ? "One item at a time. Answer it, then save, skip or discard." : "Pick at least one source on the left."}</p>
              <div><button className="btn btn-primary" disabled={!canGenerate || gen.generate.isPending} onClick={() => run(seen)}>{gen.generate.isPending ? "Generating…" : "Generate"}</button></div>
              {gen.generate.isError && (
                <div className="banner banner-error"><span className="grow">{errorMessage(gen.generate.error)}</span><button className="btn btn-sm" onClick={() => run(seen)}>Retry</button></div>
              )}
            </div>
          ) : (
            <>
              <div className="gen-card stack" aria-live="polite">
                <div className="row">
                  <span className="mono small muted">{noun} {count}</span>
                  <span className="spacer" />
                  {item.ref && <span className="small muted">{item.ref.replace(/^PYQ/, "Similar to PYQ")}</span>}
                </div>
                {gen.generate.isPending && <p className="small muted">Generating the next one…</p>}
                {isQA ? <p className="gen-front">{item.front}</p> : (
                  <>
                    {item.title && <p className="gen-front">{item.title}</p>}
                    <p className="note-text">{item.body}</p>
                  </>
                )}
                <div className="row saves-to">
                  <span className="small text-2">Saves to</span>
                  <select className="dest-chip" aria-label="Saves to" value={destIdx} onChange={(e) => setDestIdx(Number(e.target.value))}>
                    {dests.data?.map((d, i) => <option key={i} value={i}>{d.label}</option>)}
                  </select>
                </div>
                {item.type === "questions" && (
                  <>
                    <label className="field" htmlFor="gen-answer"><span>Your answer</span></label>
                    <textarea id="gen-answer" className="textarea" rows={3} value={answer} readOnly={revealed} onChange={(e) => setAnswer(e.target.value)}
                      placeholder="Work it out, then write your final line here…" />
                  </>
                )}
                {grade && <p className={`grade grade-${grade.verdict}`}><strong>{VERDICT[grade.verdict]}.</strong> {grade.feedback}</p>}
                {gen.check.isError && <p className="banner banner-error small">{errorMessage(gen.check.error)}</p>}
                {revealed && isQA && <div className="stack-tight"><span className="small muted">Answer</span><p className="note-text">{item.back}</p></div>}
                <div className="row wrap">
                  {item.type === "questions" && !revealed && (
                    <>
                      <button className="btn btn-dark" disabled={!answer.trim() || gen.check.isPending}
                        onClick={() => gen.check.mutate({ question: item.front, reference: item.back, answer, sources: item.sources },
                          { onSuccess: (g) => { setGrade(g); setRevealed(true); } })}>
                        {gen.check.isPending ? "Checking…" : "Check my answer"}
                      </button>
                      <button className="link-muted" onClick={() => setRevealed(true)}>Skip, show answer</button>
                    </>
                  )}
                  {item.type === "flashcards" && !revealed && <button className="btn" onClick={() => setRevealed(true)}>Show answer</button>}
                  <span className="spacer" />
                  <span className="tag-ai">AI answers · check them</span>
                </div>
              </div>
              <div className="gen-actions">
                <button className="btn" onClick={discard}>Discard</button>
                <button className="btn" onClick={next} disabled={gen.generate.isPending}>Next →</button>
                <button className="btn btn-primary" onClick={save} disabled={gen.save.isPending}>{isQA ? "Save + review later" : "Save"}</button>
              </div>
              {gen.save.isError && <p className="banner banner-error small">{errorMessage(gen.save.error)}</p>}
              {gen.generate.isError && <p className="banner banner-error small">{errorMessage(gen.generate.error)}</p>}
              <p className="small text-2 center">{isQA ? "Saved questions come back in your review queue, not just a list." : `Saves to ${destLabel}.`}</p>
              <p className="hint center">D discard · → next · S save</p>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
