import { useEffect, useState } from "react";
import { errorMessage } from "../api/client";
import { useTestMe, type GradeResult, type TestQuestion } from "../api/testme";
import type { SlideRef } from "../api/types";
import { Modal } from "./Modal";

const VERDICT: Record<GradeResult["verdict"], string> = { correct: "Correct", partly: "Partly", wrong: "Not quite" };

interface Props {
  courseId: string;
  lectureId: string;
  nodeId: string;
  nodeLabel: string;
  onClose: () => void;
  onPreview: (refs: SlideRef[], start: number) => void;
}

export function TestMe({ courseId, lectureId, nodeId, nodeLabel, onClose, onPreview }: Props) {
  const t = useTestMe(courseId, lectureId, nodeId);
  const [qs, setQs] = useState<TestQuestion[]>([]);
  const [answers, setAnswers] = useState<string[]>([]);
  const [results, setResults] = useState<GradeResult[] | null>(null);
  const [score, setScore] = useState<number | null>(null);

  const start = () => {
    setResults(null);
    setScore(null);
    t.start.mutate(undefined, {
      onSuccess: (r) => {
        setQs(r.questions);
        setAnswers(r.questions.map(() => ""));
      },
    });
  };
  useEffect(start, []); // eslint-disable-line react-hooks/exhaustive-deps

  const submit = () =>
    t.grade.mutate(
      qs.map((q, i) => ({ question: q.question, answer: answers[i] ?? "", source: q.source })),
      {
        onSuccess: (rec) => {
          setResults(rec.details.items ?? []);
          setScore(rec.score);
        },
      },
    );

  return (
    <Modal title={`Test me · ${nodeLabel}`} onClose={onClose} wide>
      {t.start.isPending && <p className="muted">Writing 3 questions from this topic's slides…</p>}
      {t.start.isError && (
        <div className="banner banner-error">
          <span>{errorMessage(t.start.error)}</span>
          <span className="spacer" />
          <button className="btn btn-sm" onClick={start}>Retry</button>
        </div>
      )}
      {qs.length > 0 && (
        <form className="stack" onSubmit={(e) => { e.preventDefault(); if (!results) submit(); }}>
          {qs.map((q, i) => {
            const r = results?.[i];
            return (
              <div key={q.id} className="test-q stack-tight">
                <label className="field" htmlFor={`tq-${q.id}`}>
                  <span className="test-q-text">{i + 1}. {q.question}</span>
                </label>
                <textarea
                  id={`tq-${q.id}`}
                  className="textarea"
                  rows={2}
                  value={answers[i] ?? ""}
                  readOnly={Boolean(results)}
                  onChange={(e) => setAnswers((a) => a.map((x, j) => (j === i ? e.target.value : x)))}
                  placeholder="Your answer, in your own words"
                />
                {r && (
                  <p className={`grade grade-${r.verdict} small`}>
                    <strong>{VERDICT[r.verdict]}.</strong> {r.feedback}{" "}
                    {r.source && (
                      <button type="button" className="chip" onClick={() => onPreview([r.source!], 0)}>Slide {r.source.slide}</button>
                    )}
                  </p>
                )}
              </div>
            );
          })}
          {t.grade.isError && (
            <div className="banner banner-error">
              <span>{errorMessage(t.grade.error)}</span>
              <span className="spacer" />
              <button type="button" className="btn btn-sm" onClick={submit}>Retry</button>
            </div>
          )}
          <div className="row">
            {score !== null && <span className="mono">{Math.round(score * 100)}%</span>}
            {score !== null && <span className="small muted">Saved to this topic's history.</span>}
            <span className="spacer" />
            {results ? (
              <>
                <button type="button" className="btn" onClick={start}>New questions</button>
                <button type="button" className="btn btn-primary" onClick={onClose}>Done</button>
              </>
            ) : (
              <button type="submit" className="btn btn-primary" disabled={t.grade.isPending}>
                {t.grade.isPending ? "Checking…" : "Check answers"}
              </button>
            )}
          </div>
        </form>
      )}
    </Modal>
  );
}
