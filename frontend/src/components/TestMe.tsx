import { useEffect, useState } from "react";
import { errorMessage } from "../api/client";
import { useTestMe, type GradeResult, type TestQuestion } from "../api/testme";
import type { SlideRef } from "../api/types";
import { Modal } from "./Modal";

const VERDICT: Record<GradeResult["verdict"], string> = { correct: "Correct", partly: "Partly", wrong: "Wrong" };

interface Props {
  courseId: string;
  lectureId: string;
  nodeId: string;
  nodeLabel: string;
  onClose: () => void;
  onPreview: (refs: SlideRef[], start: number) => void;
}

/** UI.md §3.4: one question at a time, Check (dark), result row, Next →, score summary. */
export function TestMe({ courseId, lectureId, nodeId, nodeLabel, onClose, onPreview }: Props) {
  const t = useTestMe(courseId, lectureId, nodeId);
  const [qs, setQs] = useState<TestQuestion[]>([]);
  const [i, setI] = useState(0);
  const [answers, setAnswers] = useState<string[]>([]);
  const [checked, setChecked] = useState<GradeResult[]>([]);
  const [score, setScore] = useState<number | null>(null);

  const start = () => {
    setI(0); setChecked([]); setScore(null);
    t.start.mutate(undefined, { onSuccess: (r) => { setQs(r.questions); setAnswers(r.questions.map(() => "")); } });
  };
  useEffect(start, []); // eslint-disable-line react-hooks/exhaustive-deps

  const q = qs[i];
  const result = checked[i];
  const last = i === qs.length - 1;

  // Check grades this one answer; after the last, the whole test is saved to results.jsonl.
  const check = () =>
    t.grade.mutate(
      { items: [{ question: q!.question, answer: answers[i] ?? "", source: q!.source }], save: false },
      {
        onSuccess: (rec) => {
          const r = rec.details.items?.[0];
          if (!r) return;
          const all = [...checked.slice(0, i), r];
          setChecked(all);
          if (last) t.save.mutate(all, { onSuccess: (saved) => setScore(saved.score) });
        },
      },
    );

  return (
    <Modal title={`Test me · ${nodeLabel}`} onClose={onClose}>
      {t.start.isPending && <p className="muted">Writing 3 questions from this topic's slides…</p>}
      {t.start.isError && (
        <div className="banner banner-error">
          <span className="grow">{errorMessage(t.start.error)}</span>
          <button className="btn btn-sm" onClick={start}>Retry</button>
        </div>
      )}
      {score !== null ? (
        <div className="stack">
          <p className="test-score"><span className="mono">{Math.round(score * 100)}%</span> · {checked.filter((r) => r.verdict === "correct").length} of {qs.length} correct</p>
          <ul className="note-list">
            {checked.map((r, j) => (
              <li key={j} className={`grade grade-${r.verdict}`}><strong>{VERDICT[r.verdict]}</strong> {qs[j]?.question}</li>
            ))}
          </ul>
          <p className="small muted">Saved to this topic's history.</p>
          <div className="row">
            <button className="btn" onClick={start}>New questions</button>
            <span className="spacer" />
            <button className="btn btn-primary" onClick={onClose}>Back to topic</button>
          </div>
        </div>
      ) : q && (
        <form className="stack" onSubmit={(e) => { e.preventDefault(); if (!result) check(); else if (!last) setI(i + 1); }}>
          <p className="mono small muted">{i + 1} / {qs.length}</p>
          <label htmlFor={`tq-${q.id}`} className="test-q-text">{q.question}</label>
          <textarea id={`tq-${q.id}`} className="textarea" rows={3} value={answers[i] ?? ""} readOnly={Boolean(result)}
            placeholder="Your answer" onChange={(e) => setAnswers((a) => a.map((x, j) => (j === i ? e.target.value : x)))} />
          {result && last && t.save.isPending && <p className="small muted">Saving…</p>}
          {result && (
            <p className={`grade grade-${result.verdict}`}>
              <strong>{VERDICT[result.verdict]}.</strong> {result.feedback}{" "}
              {result.source && <button type="button" className="slide-chip" onClick={() => onPreview([result.source!], 0)}>Slide {result.source.slide}</button>}
            </p>
          )}
          {t.grade.isError && (
            <div className="banner banner-error">
              <span className="grow">{errorMessage(t.grade.error)}</span>
              <button type="button" className="btn btn-sm" onClick={check}>Retry</button>
            </div>
          )}
          <div className="row">
            <span className="spacer" />
            {!result ? (
              <button type="submit" className="btn btn-dark" disabled={t.grade.isPending}>{t.grade.isPending ? "Checking…" : "Check"}</button>
            ) : !last ? (
              <button type="submit" className="btn btn-primary">Next →</button>
            ) : null}
          </div>
        </form>
      )}
    </Modal>
  );
}
