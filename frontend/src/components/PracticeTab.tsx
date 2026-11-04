import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api, errorMessage } from "../api/client";
import { useHistory, useNodePractice } from "../api/testme";
import type { PracticeItem } from "../api/types";

/** Practice tab (SPEC §5.12): the node's cards + saved questions; add / edit / delete; cards from slides. */
export function PracticeTab({ courseId, lectureId, nodeId }: { courseId: string; lectureId: string; nodeId: string }) {
  const items = useNodePractice(courseId, lectureId, nodeId);
  const history = useHistory(courseId, lectureId, nodeId);
  const qc = useQueryClient();
  const base = `/courses/${courseId}/lectures/${lectureId}`;
  const refresh = () => {
    void qc.invalidateQueries({ queryKey: ["practice", courseId, lectureId, nodeId] });
    void qc.invalidateQueries({ queryKey: ["due-counts"] });
  };
  const patch = useMutation({
    mutationFn: ({ id, ...b }: { id: string; front?: string; back?: string; answer_status?: string }) =>
      api(`${base}/practice/${id}`, { method: "PATCH", json: b }),
    onSuccess: refresh,
  });
  const remove = useMutation({ mutationFn: (id: string) => api(`${base}/practice/${id}`, { method: "DELETE" }), onSuccess: refresh });
  const add = useMutation({
    mutationFn: (b: { type: "card" | "question"; front: string; back: string }) => api(`${base}/practice`, { method: "POST", json: { ...b, node_id: nodeId } }),
    onSuccess: refresh,
  });
  const fromSlides = useMutation({
    mutationFn: () => api<PracticeItem[]>(`${base}/nodes/${nodeId}/practice/cards`, { method: "POST" }),
    onSuccess: refresh,
  });
  const [draft, setDraft] = useState<{ type: "card" | "question"; front: string; back: string } | null>(null);
  const [editing, setEditing] = useState<{ id: string; front: string; back: string } | null>(null);

  return (
    <div className="stack practice-tab">
      <div className="row wrap">
        <button className="btn btn-sm" onClick={() => fromSlides.mutate()} disabled={fromSlides.isPending}>
          {fromSlides.isPending ? "Making cards…" : "Make 3 cards from slides"}
        </button>
        <button className="btn btn-sm" onClick={() => setDraft({ type: "card", front: "", back: "" })}>+ Write a card</button>
      </div>
      {fromSlides.isError && (
        <div className="banner banner-error small"><span className="grow">{errorMessage(fromSlides.error)}</span><button className="btn btn-sm" onClick={() => fromSlides.mutate()}>Retry</button></div>
      )}
      {draft && (
        <form className="note stack-tight" onSubmit={(e) => { e.preventDefault(); add.mutate(draft, { onSuccess: () => setDraft(null) }); }}>
          <div className="row">
            <button type="button" className="chip" aria-pressed={draft.type === "card"} onClick={() => setDraft({ ...draft, type: "card" })}>Flashcard</button>
            <button type="button" className="chip" aria-pressed={draft.type === "question"} onClick={() => setDraft({ ...draft, type: "question" })}>Question</button>
          </div>
          <input className="input" aria-label="Front" autoFocus value={draft.front} onChange={(e) => setDraft({ ...draft, front: e.target.value })} placeholder="Front: a question or cue" />
          <textarea className="textarea" aria-label="Back" rows={2} value={draft.back} onChange={(e) => setDraft({ ...draft, back: e.target.value })} placeholder="Back: the answer" />
          <div className="row"><span className="spacer" /><button type="button" className="btn btn-ghost btn-sm" onClick={() => setDraft(null)}>Cancel</button><button className="btn btn-sm btn-primary" disabled={!draft.front.trim()}>Add</button></div>
        </form>
      )}
      <section className="stack-tight">
        <h3>Cards and saved questions</h3>
        {items.data?.length === 0 && <p className="muted small">None yet. Make some from the slides, a kept question, a note, or Generate.</p>}
        <ul className="note-list">
          {items.data?.map((it) => (
            <li key={it.id} className="note">
              {editing?.id === it.id ? (
                <form className="stack-tight" onSubmit={(e) => { e.preventDefault(); patch.mutate(editing, { onSuccess: () => setEditing(null) }); }}>
                  <input className="input" aria-label="Front" value={editing.front} onChange={(e) => setEditing({ ...editing, front: e.target.value })} />
                  <textarea className="textarea" aria-label="Back" rows={2} value={editing.back} onChange={(e) => setEditing({ ...editing, back: e.target.value })} />
                  <div className="row"><span className="spacer" /><button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditing(null)}>Cancel</button><button className="btn btn-sm">Save</button></div>
                </form>
              ) : (
                <>
                  <p className="xsmall muted">{it.type === "card" ? "Flashcard" : "Question"}{it.fsrs ? ` · next ${new Date(String(it.fsrs.due)).toLocaleDateString()}` : " · new"}{it.answer_status === "ai_unverified" ? " · AI answer · check it" : ""}{it.origin.ref ? ` · ${it.origin.ref}` : ""}</p>
                  <p className="note-text"><strong>{it.front}</strong></p>
                  {it.back && <details><summary className="small muted">Answer</summary><p className="note-text">{it.back}</p></details>}
                  <div className="row">
                    <span className="spacer" />
                    {it.answer_status === "ai_unverified" && <button className="btn btn-ghost btn-sm" onClick={() => patch.mutate({ id: it.id, answer_status: "verified" })}>Mark verified</button>}
                    <button className="btn btn-ghost btn-sm" onClick={() => setEditing({ id: it.id, front: it.front, back: it.back })}>Edit</button>
                    <button className="btn btn-ghost btn-sm" onClick={() => window.confirm("Delete this item?") && remove.mutate(it.id)}>Delete</button>
                  </div>
                </>
              )}
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
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
