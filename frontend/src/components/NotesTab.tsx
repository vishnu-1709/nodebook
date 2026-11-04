import { useState } from "react";
import { useLectureNotes, useNoteMutations } from "../api/notes";

export function NotesTab({ courseId, lectureId, nodeId }: { courseId: string; lectureId: string; nodeId: string }) {
  const notes = useLectureNotes(courseId, lectureId, nodeId);
  const m = useNoteMutations(courseId, lectureId);
  const [text, setText] = useState("");
  const [editing, setEditing] = useState<{ id: string; text: string } | null>(null);

  return (
    <div className="stack notes-tab">
      <form
        className="stack-tight"
        onSubmit={(e) => {
          e.preventDefault();
          if (text.trim()) m.add.mutate({ text, node_id: nodeId }, { onSuccess: () => setText("") });
        }}
      >
        <label className="visually-hidden" htmlFor="node-note">New note</label>
        <textarea id="node-note" className="textarea" rows={2} value={text} onChange={(e) => setText(e.target.value)}
          placeholder="Write a note in your own words…" />
        <div className="row"><span className="spacer" /><button className="btn btn-sm" disabled={!text.trim()}>Add note</button></div>
      </form>
      {notes.data?.length === 0 && <p className="muted small">No notes on this topic yet.</p>}
      <ul className="note-list">
        {notes.data?.slice().reverse().map((n) => (
          <li key={n.id} className="note">
            {editing?.id === n.id ? (
              <form className="stack-tight" onSubmit={(e) => { e.preventDefault(); m.edit.mutate(editing, { onSuccess: () => setEditing(null) }); }}>
                <textarea className="textarea" aria-label="Edit note" value={editing.text} onChange={(e) => setEditing({ ...editing, text: e.target.value })} />
                <div className="row">
                  <span className="spacer" />
                  <button type="button" className="btn btn-ghost btn-sm" onClick={() => setEditing(null)}>Cancel</button>
                  <button className="btn btn-sm" disabled={!editing.text.trim()}>Save</button>
                </div>
              </form>
            ) : (
              <>
                <p className="note-text">{n.text}</p>
                <div className="row">
                  <span className="small muted">{new Date(n.created_at).toLocaleDateString()}{n.pinned_from ? " · from a question" : ""}</span>
                  <span className="spacer" />
                  <button className="btn btn-ghost btn-sm" onClick={() => setEditing({ id: n.id, text: n.text })}>Edit</button>
                  <button className="btn btn-ghost btn-sm" onClick={() => window.confirm("Delete this note?") && m.remove.mutate(n.id)}>Delete</button>
                </div>
              </>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
