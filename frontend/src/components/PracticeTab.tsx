import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { useHistory, useNodePractice } from "../api/testme";

export function PracticeTab({ courseId, lectureId, nodeId }: { courseId: string; lectureId: string; nodeId: string }) {
  const items = useNodePractice(courseId, lectureId, nodeId);
  const history = useHistory(courseId, lectureId, nodeId);
  const qc = useQueryClient();
  const verify = useMutation({
    mutationFn: (id: string) =>
      api(`/courses/${courseId}/lectures/${lectureId}/practice/${id}`, { method: "PATCH", json: { answer_status: "verified" } }),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ["practice", courseId, lectureId, nodeId] }),
  });
  return (
    <div className="stack practice-tab">
      <section className="stack-tight">
        <h3>Cards and saved questions</h3>
        {items.data?.length === 0 && <p className="muted small">None yet. Make one from a kept question or Generate.</p>}
        <ul className="note-list">
          {items.data?.map((it) => (
            <li key={it.id} className="note">
              <p className="small muted">{it.type === "card" ? "Card" : "Question"}{it.answer_status === "ai_unverified" ? " · AI answer · check it" : ""}</p>
              <p className="note-text"><strong>{it.front}</strong></p>
              {it.back && (
                <details>
                  <summary className="small muted">Answer</summary>
                  <p className="note-text">{it.back}</p>
                  {it.answer_status === "ai_unverified" && (
                    <button className="btn btn-ghost btn-sm" onClick={() => verify.mutate(it.id)}>Mark answer as verified</button>
                  )}
                </details>
              )}
              {it.origin.ref && <p className="small muted">{it.origin.ref}</p>}
            </li>
          ))}
        </ul>
      </section>
      <section className="stack-tight">
        <h3>History</h3>
        {history.data?.length === 0 && <p className="muted small">No tests yet. Use “Test me”.</p>}
        <ul className="note-list">
          {history.data?.map((r) => (
            <li key={r.id} className="note">
              <div className="row">
                <span>{r.kind === "test_me" ? "Test me" : r.kind === "recall" ? "Blank-map recall" : "Explain it back"}</span>
                <span className="spacer" />
                <span className="mono small">{Math.round(r.score * 100)}%</span>
                <span className="small muted">{new Date(r.created_at).toLocaleDateString()}</span>
              </div>
              {r.details.items && (
                <details>
                  <summary className="small muted">Details</summary>
                  <ul className="small">
                    {r.details.items.map((g, i) => <li key={i}><strong>{g.verdict}</strong> — {g.question} <span className="muted">{g.feedback}</span></li>)}
                  </ul>
                </details>
              )}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
