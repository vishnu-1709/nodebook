import { useEffect, useMemo, useState } from "react";
import { errorMessage } from "../api/client";
import { useGenDestinations, useGenerate, type Chip, type GenType, type GeneratedItem } from "../api/generate";
import { useCourse, useCourses } from "../api/hooks";
import { useSources } from "../api/lectures";
import type { MapDoc } from "../api/types";
import { SOURCE_KIND_LABEL } from "../api/types";
import type { GradeResult } from "../api/testme";
import { isTypingTarget } from "../app/shortcuts";
import { useUi } from "../app/store";
import { useQueryClient } from "@tanstack/react-query";
import { lk } from "../api/lectures";
import { Modal } from "./Modal";

const TYPES: { id: GenType; label: string }[] = [
  { id: "questions", label: "Practice questions" },
  { id: "flashcards", label: "Flashcards" },
  { id: "summary", label: "Summary" },
  { id: "explain", label: "Explain a topic" },
];
const CHIPS: { id: Chip; label: string }[] = [
  { id: "harder", label: "Harder" },
  { id: "easier", label: "Easier" },
  { id: "conceptual", label: "Conceptual" },
  { id: "numerical", label: "Numerical" },
];
const VERDICT: Record<GradeResult["verdict"], string> = { correct: "Correct", partly: "Partly", wrong: "Not quite" };

export function GeneratePanel({ onClose }: { onClose: () => void }) {
  const ctx = useUi((s) => s.context);
  const showToast = useUi((s) => s.showToast);
  const courses = useCourses();
  const [courseId, setCourseId] = useState<string | null>(ctx.courseId);
  useEffect(() => {
    if (!courseId && courses.data?.length === 1) setCourseId(courses.data[0]!.id);
  }, [courseId, courses.data]);

  const course = useCourse(courseId ?? undefined);
  const sources = useSources(courseId ?? "");
  const dests = useGenDestinations(courseId);
  const gen = useGenerate(courseId ?? "");
  const qc = useQueryClient();

  const [lectureIds, setLectureIds] = useState<string[]>(ctx.lectureId ? [ctx.lectureId] : []);
  const [sourceIds, setSourceIds] = useState<string[]>([]);
  const [type, setType] = useState<GenType>("questions");
  const [steer, setSteer] = useState("");
  const [chips, setChips] = useState<Chip[]>([]);
  const ctxMap = ctx.courseId && ctx.lectureId ? qc.getQueryData<MapDoc>(lk.map(ctx.courseId, ctx.lectureId)) : undefined;
  const [topic, setTopic] = useState(ctx.nodeId ? ctxMap?.nodes[ctx.nodeId]?.label ?? "" : "");

  const [item, setItem] = useState<GeneratedItem | null>(null);
  const [seen, setSeen] = useState<string[]>([]);
  const [answer, setAnswer] = useState("");
  const [grade, setGrade] = useState<GradeResult | null>(null);
  const [revealed, setRevealed] = useState(false);
  const [destIdx, setDestIdx] = useState<number>(-1);

  const shelf = useMemo(() => (sources.data ?? []).filter((s) => !s.lecture_id), [sources.data]);
  const canGenerate = Boolean(courseId) && (lectureIds.length > 0 || sourceIds.length > 0) && (type !== "explain" || topic.trim());

  const run = (exclude: string[]) => {
    setGrade(null);
    setAnswer("");
    setRevealed(false);
    gen.generate.mutate(
      { type, source_ids: sourceIds, lecture_ids: lectureIds, steer, chips, topic, exclude },
      {
        onSuccess: (it) => {
          setItem(it);
          setSeen((s) => [...s, it.key]);
          const list = dests.data ?? [];
          const i = list.findIndex((d) => it.suggested && d.node_id === it.suggested.node_id && d.lecture_id === it.suggested.lecture_id);
          setDestIdx(i >= 0 ? i : 0);
        },
      },
    );
  };

  const next = () => run(seen);
  const discard = () => {
    setItem(null);
    setGrade(null);
  };
  const save = () => {
    if (!item || !courseId) return;
    const d = dests.data?.[destIdx] ?? { course_id: courseId, lecture_id: null, node_id: null, label: "Course (unassigned)" };
    gen.save.mutate(
      { item, destination: d },
      {
        onSuccess: () => {
          showToast(`Saved to ${d.label}`);
          next();
        },
      },
    );
  };

  // D / → / S while not typing
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

  return (
    <Modal title="Generate" onClose={onClose} wide>
      {!ctx.courseId && (
        <label className="field">
          <span>Course</span>
          <select className="select" value={courseId ?? ""} onChange={(e) => { setCourseId(e.target.value); setLectureIds([]); setSourceIds([]); }}>
            <option value="" disabled>Choose a course…</option>
            {courses.data?.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </label>
      )}
      {courseId && (
        <>
          <fieldset className="gen-fieldset">
            <legend className="small muted">From</legend>
            <div className="chips">
              {course.data?.lectures.map((l) => (
                <button key={l.id} type="button" className={lectureIds.includes(l.id) ? "chip active" : "chip"}
                  aria-pressed={lectureIds.includes(l.id)} onClick={() => toggle(lectureIds, l.id, setLectureIds)}>
                  {l.title}
                </button>
              ))}
              {shelf.map((s) => (
                <button key={s.id} type="button" className={sourceIds.includes(s.id) ? "chip active" : "chip"}
                  aria-pressed={sourceIds.includes(s.id)} onClick={() => toggle(sourceIds, s.id, setSourceIds)}>
                  {s.filename} <span className="muted">· {SOURCE_KIND_LABEL[s.kind]}</span>
                </button>
              ))}
              {course.data?.lectures.length === 0 && shelf.length === 0 && <span className="small muted">This course has no files yet.</span>}
            </div>
          </fieldset>
          <div className="segmented" role="radiogroup" aria-label="Type">
            {TYPES.map((t) => (
              <button key={t.id} type="button" role="radio" aria-checked={type === t.id}
                className={type === t.id ? "seg active" : "seg"} onClick={() => setType(t.id)}>{t.label}</button>
            ))}
          </div>
          {type === "explain" && (
            <label className="field">
              <span>Topic</span>
              <input className="input" value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="e.g. Ridge regression" />
            </label>
          )}
          <div className="row wrap">
            <input className="input grow" aria-label="Steer (optional)" value={steer} onChange={(e) => setSteer(e.target.value)}
              placeholder="Optional: steer it, e.g. “like Q4 of the 2023 paper”" />
            {CHIPS.map((c) => (
              <button key={c.id} type="button" className={chips.includes(c.id) ? "chip active" : "chip"} aria-pressed={chips.includes(c.id)}
                onClick={() => toggle(chips, c.id, setChips)}>{c.label}</button>
            ))}
          </div>
          {!item && (
            <div className="row">
              <span className="spacer" />
              <button className="btn btn-primary" disabled={!canGenerate || gen.generate.isPending} onClick={() => run(seen)}>
                {gen.generate.isPending ? "Generating…" : "Generate"}
              </button>
            </div>
          )}
        </>
      )}

      {gen.generate.isError && (
        <div className="banner banner-error">
          <span>{errorMessage(gen.generate.error)}</span>
          <span className="spacer" />
          <button className="btn btn-sm" onClick={() => run(seen)}>Retry</button>
        </div>
      )}

      {item && (
        <section className="gen-result card stack" aria-live="polite">
          {gen.generate.isPending && <p className="small muted">Generating the next one…</p>}
          {item.ref && <p className="small muted">{item.ref}</p>}
          {isQA ? (
            <>
              <p className="gen-front">{item.front}</p>
              {item.type === "questions" && !revealed && (
                <>
                  <label className="visually-hidden" htmlFor="gen-answer">Your answer</label>
                  <textarea id="gen-answer" className="textarea" rows={3} value={answer} onChange={(e) => setAnswer(e.target.value)}
                    placeholder="Answer first, in your own words" />
                  <div className="row">
                    <button className="btn btn-sm btn-primary" disabled={!answer.trim() || gen.check.isPending}
                      onClick={() => gen.check.mutate({ question: item.front, reference: item.back, answer, sources: item.sources },
                        { onSuccess: (g) => { setGrade(g); setRevealed(true); } })}>
                      {gen.check.isPending ? "Checking…" : "Check my answer"}
                    </button>
                    <button className="btn btn-ghost btn-sm subtle" onClick={() => setRevealed(true)}>Skip, show answer</button>
                  </div>
                </>
              )}
              {item.type === "flashcards" && !revealed && (
                <button className="btn btn-sm" onClick={() => setRevealed(true)}>Show answer</button>
              )}
              {grade && <p className={`grade grade-${grade.verdict} small`}><strong>{VERDICT[grade.verdict]}.</strong> {grade.feedback}</p>}
              {gen.check.isError && <p className="banner banner-error small">{errorMessage(gen.check.error)}</p>}
              {revealed && (
                <div className="stack-tight">
                  <span className="tag-unverified small">AI answer · check it</span>
                  <p className="note-text">{item.back}</p>
                </div>
              )}
            </>
          ) : (
            <>
              {item.title && <h3>{item.title}</h3>}
              <p className="note-text">{item.body}</p>
              <span className="tag-unverified small">AI-written · check it against your slides</span>
            </>
          )}
          {item.sources.length > 0 && (
            <p className="small muted">From: {item.sources.map((s) => `p. ${s.slide}`).join(", ")}</p>
          )}
          <div className="row wrap">
            <label className="field grow">
              <span>Saves to</span>
              <select className="select" value={destIdx} onChange={(e) => setDestIdx(Number(e.target.value))}>
                {dests.data?.map((d, i) => <option key={i} value={i}>{d.label}</option>)}
              </select>
            </label>
          </div>
          {gen.save.isError && <p className="banner banner-error small">{errorMessage(gen.save.error)}</p>}
          <div className="row">
            <button className="btn" onClick={discard}>Discard <span className="kbd">D</span></button>
            <span className="spacer" />
            <button className="btn" onClick={next} disabled={gen.generate.isPending}>Next <span className="kbd">→</span></button>
            <button className="btn btn-primary" onClick={save} disabled={gen.save.isPending}>Save <span className="kbd">S</span></button>
          </div>
        </section>
      )}
    </Modal>
  );
}
