import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, errorMessage } from "../api/client";
import type { SlideRef } from "../api/types";
import { Modal } from "./Modal";

interface Cited { point: string; correction: string; source: SlideRef | null }
interface Review { covered: string[]; missing: Cited[]; wrong: Cited[]; score: number }

/** Explain-it-back (SPEC §5.13): the student explains; the AI lists what's missing or wrong, citing slides. */
export function ExplainBack({ courseId, lectureId, nodeId, nodeLabel, onClose, onPreview }: {
  courseId: string; lectureId: string; nodeId: string; nodeLabel: string; onClose: () => void; onPreview: (refs: SlideRef[], start: number) => void;
}) {
  const [text, setText] = useState("");
  const qc = useQueryClient();
  const m = useMutation({
    mutationFn: () => api<{ review: Review }>(`/courses/${courseId}/lectures/${lectureId}/nodes/${nodeId}/explain-back`, { method: "POST", json: { text } }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["history"] }),
  });
  const r = m.data?.review;
  const chip = (c: Cited) => c.source && <button className="slide-chip" onClick={() => onPreview([c.source!], 0)}>Slide {c.source.slide}</button>;
  return (
    <Modal title={`Explain it back · ${nodeLabel}`} onClose={onClose} wide>
      <p className="small text-2">Explain this topic in your own words, as if to a friend. Then see what you missed.</p>
      <textarea className="textarea" rows={6} aria-label="Your explanation" value={text} readOnly={Boolean(r)} onChange={(e) => setText(e.target.value)} />
      {m.isError && (
        <div className="banner banner-error small"><span className="grow">{errorMessage(m.error)}</span><button className="btn btn-sm" onClick={() => m.mutate()}>Retry</button></div>
      )}
      {r && (
        <div className="stack">
          <p className="test-score"><span className="mono">{Math.round(r.score * 100)}%</span> covered</p>
          {r.wrong.length > 0 && (
            <section className="stack-tight"><h3>Not quite right</h3>
              <ul className="note-list">{r.wrong.map((c, i) => <li key={i} className="grade grade-wrong"><span className="grow"><strong>{c.point}</strong>{c.correction ? ` — ${c.correction}` : ""}</span>{chip(c)}</li>)}</ul>
            </section>
          )}
          {r.missing.length > 0 && (
            <section className="stack-tight"><h3>Missing</h3>
              <ul className="note-list">{r.missing.map((c, i) => <li key={i} className="grade grade-partly"><span className="grow">{c.point}</span>{chip(c)}</li>)}</ul>
            </section>
          )}
          {r.covered.length > 0 && (
            <section className="stack-tight"><h3>You covered</h3>
              <ul className="note-list">{r.covered.map((c, i) => <li key={i} className="grade grade-correct">{c}</li>)}</ul>
            </section>
          )}
        </div>
      )}
      <div className="row">
        <span className="spacer" />
        {r ? (
          <>
            <button className="btn" onClick={() => { m.reset(); }}>Edit and try again</button>
            <button className="btn btn-primary" onClick={onClose}>Back to topic</button>
          </>
        ) : (
          <button className="btn btn-dark" disabled={!text.trim() || m.isPending} onClick={() => m.mutate()}>{m.isPending ? "Checking…" : "Check my explanation"}</button>
        )}
      </div>
    </Modal>
  );
}
