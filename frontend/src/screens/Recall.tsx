import { useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, errorMessage } from "../api/client";
import { useLecture, useMap } from "../api/lectures";
import type { MapDoc } from "../api/types";
import { useModalLayer } from "../components/Modal";
import { PomodoroChip } from "../components/PomodoroChip";

interface Verdict { node_id: string; expected: string; typed: string; correct: boolean; how: string }
interface RecallOut { verdicts: Verdict[]; correct: number; total: number; score: number }

/** Blank-map recall (SPEC §5.13): labels hidden; type the label for each node position. */
export function RecallScreen() {
  const { courseId = "", lectureId = "" } = useParams();
  const nav = useNavigate();
  const back = () => nav(`/course/${courseId}/lecture/${lectureId}`);
  useModalLayer(back);
  const lecture = useLecture(courseId, lectureId);
  const map = useMap(courseId, lectureId, true);
  const qc = useQueryClient();
  const [typed, setTyped] = useState<Record<string, string>>({});
  const judge = useMutation({
    mutationFn: () => api<RecallOut>(`/courses/${courseId}/lectures/${lectureId}/recall/judge`, {
      method: "POST",
      json: { answers: order(map.data).map((id) => ({ node_id: id, typed: typed[id] ?? "" })) },
    }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["history"] }),
  });
  const result = judge.data;
  const byId = useMemo(() => Object.fromEntries((result?.verdicts ?? []).map((v) => [v.node_id, v])), [result]);
  const doc = map.data;
  const filled = Object.values(typed).filter((t) => t.trim()).length;

  return (
    <div className="fullscreen recall-screen" role="dialog" aria-modal="true" aria-label="Blank-map recall">
      <header className="review-head">
        <button className="btn btn-ghost btn-sm" onClick={back}>✕ Back to map</button>
        <span className="screen-title">Recall test · {lecture.data?.title}</span>
        <span className="spacer" />
        {result ? (
          <span className="mono">{result.correct} / {result.total} · {Math.round(result.score * 100)}%</span>
        ) : (
          <span className="small text-2">{filled} of {doc ? order(doc).length : 0} filled</span>
        )}
        <PomodoroChip />
      </header>
      <p className="small text-2 recall-intro">
        {result ? "Green: you had it. Orange: here's what it was. Each node's result is saved to its history."
          : "Rebuild the map from memory: type the label for each box. Slide numbers are hints. Synonyms count."}
      </p>
      <main className="recall-main">
        {doc && (
          <div className="rc-tree">
            <div className="rc-row">
              <div className="rc-box rc-root">{doc.nodes[doc.root_id]?.label}</div>
              <div className="rc-kids">
                {doc.nodes[doc.root_id]?.children.map((c) => (
                  <RecallNode key={c} doc={doc} id={c} typed={typed} setTyped={setTyped} verdicts={byId} locked={Boolean(result)} />
                ))}
              </div>
            </div>
          </div>
        )}
      </main>
      <footer className="recall-foot">
        {judge.isError && <span className="error-text small">{errorMessage(judge.error)}</span>}
        <span className="spacer" />
        {result ? (
          <>
            <button className="btn" onClick={() => { setTyped({}); judge.reset(); }}>Try again</button>
            <button className="btn btn-primary" onClick={back}>Back to map</button>
          </>
        ) : (
          <button className="btn btn-dark" disabled={!filled || judge.isPending} onClick={() => judge.mutate()}>
            {judge.isPending ? "Checking…" : "Check my map"}
          </button>
        )}
      </footer>
    </div>
  );
}

function order(doc: MapDoc | undefined): string[] {
  if (!doc) return [];
  const out: string[] = [];
  const walk = (id: string) => {
    for (const c of doc.nodes[id]?.children ?? []) {
      if (!doc.nodes[c]) continue;
      out.push(c);
      walk(c);
    }
  };
  walk(doc.root_id);
  return out;
}

function RecallNode({ doc, id, typed, setTyped, verdicts, locked }: {
  doc: MapDoc; id: string; typed: Record<string, string>; setTyped: (f: (t: Record<string, string>) => Record<string, string>) => void;
  verdicts: Record<string, Verdict>; locked: boolean;
}) {
  const n = doc.nodes[id];
  if (!n) return null;
  const v = verdicts[id];
  const slides = n.sources.map((s) => s.slide);
  const hint = slides.length ? `sl. ${slides.length > 2 ? `${Math.min(...slides)}–${Math.max(...slides)}` : slides.join(", ")}` : "";
  const cls = v ? (v.correct ? "rc-box rc-ok" : "rc-box rc-miss") : "rc-box";
  return (
    <div className="rc-row">
      <div className={cls}>
        <input
          className="rc-input"
          aria-label={`Label for a topic${hint ? ` (${hint})` : ""}`}
          value={typed[id] ?? ""}
          readOnly={locked}
          placeholder="?"
          onChange={(e) => { const val = e.target.value; setTyped((t) => ({ ...t, [id]: val })); }}
        />
        {hint && <span className="rc-hint mono">{hint}</span>}
        {v && !v.correct && <span className="rc-answer">{v.expected}</span>}
      </div>
      {n.children.length > 0 && (
        <div className="rc-kids">
          {n.children.map((c) => <RecallNode key={c} doc={doc} id={c} typed={typed} setTyped={setTyped} verdicts={verdicts} locked={locked} />)}
        </div>
      )}
    </div>
  );
}
