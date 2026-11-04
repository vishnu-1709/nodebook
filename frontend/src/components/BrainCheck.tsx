import { useEffect, useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { api, errorMessage } from "../api/client";
import type { GradeResult } from "../api/testme";
import type { SlideRef } from "../api/types";
import type { BrainCheck } from "../app/pomodoro";

interface Q { course_id: string; lecture_id: string; node_id: string; node_label: string; question: string; source: SlideRef | null }
interface Out { summary: string; questions: Q[] }
const VERDICT: Record<GradeResult["verdict"], string> = { correct: "Correct", partly: "Partly", wrong: "Not quite" };

/** End-of-session "Quick brain check" (SPEC §5.11 v0.2): 3 questions from topics touched this session. */
export function BrainCheckView({ check, onDone, onSkipBreak }: { check: BrainCheck; onDone: () => void; onSkipBreak: () => void }) {
  const load = useMutation({
    mutationFn: () => api<Out>("/brain-check", { method: "POST", json: {
      nodes: check.touched, started_at: new Date(check.startedAt).toISOString(), ended_at: new Date(check.endedAt).toISOString(), work_min: check.workMin,
    } }),
  });
  const [answers, setAnswers] = useState<string[]>([]);
  const [grades, setGrades] = useState<(GradeResult | null)[]>([]);
  const grade = useMutation({
    mutationFn: ({ q, answer }: { q: Q; answer: string }) =>
      api<{ details: { items?: GradeResult[] } }>(`/courses/${q.course_id}/lectures/${q.lecture_id}/nodes/${q.node_id}/test-me/grade`, {
        method: "POST", json: { items: [{ question: q.question, answer, source: q.source }], save: true },
      }),
  });
  useEffect(() => { load.mutate(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  const qs = load.data?.questions ?? [];

  return (
    <div className="brain stack">
      <p className="label-caps">Session done</p>
      <h2 className="break-title">{load.data?.summary ?? `${check.workMin} min`}</h2>
      {load.isPending && <p className="text-2">Picking 3 quick questions from what you studied…</p>}
      {load.isError && <p className="banner banner-error small">{errorMessage(load.error)}</p>}
      {qs.length > 0 && <p className="text-2 small">Quick brain check before your break — answer from memory.</p>}
      {qs.map((q, i) => {
        const g = grades[i];
        return (
          <div key={i} className="brain-q stack-tight">
            <p className="xsmall muted">{q.node_label}</p>
            <label htmlFor={`bq-${i}`} className="test-q-text">{q.question}</label>
            <div className="row">
              <input id={`bq-${i}`} className="input" value={answers[i] ?? ""} readOnly={Boolean(g)}
                onChange={(e) => setAnswers((a) => { const n = [...a]; n[i] = e.target.value; return n; })} />
              {!g && (
                <button className="btn btn-dark btn-sm" disabled={grade.isPending}
                  onClick={() => grade.mutate({ q, answer: answers[i] ?? "" }, {
                    onSuccess: (r) => setGrades((gs) => { const n = [...gs]; n[i] = r.details.items?.[0] ?? null; return n; }),
                  })}>Check</button>
              )}
            </div>
            {g && <p className={`grade grade-${g.verdict}`}><strong>{VERDICT[g.verdict]}.</strong> {g.feedback}</p>}
          </div>
        );
      })}
      {grade.isError && <p className="banner banner-error small">{errorMessage(grade.error)}</p>}
      <div className="row">
        <button className="btn btn-ghost" onClick={onSkipBreak}>Skip break</button>
        <span className="spacer" />
        <button className="btn btn-primary" onClick={onDone}>Start break</button>
      </div>
    </div>
  );
}
