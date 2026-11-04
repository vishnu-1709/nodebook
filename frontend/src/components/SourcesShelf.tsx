import { useState } from "react";
import { errorMessage } from "../api/client";
import { useDeleteSource, usePatchSource, useSources, useUploadSource } from "../api/lectures";
import { SOURCE_KIND_LABEL, type SourceKind } from "../api/types";
import { DropZone } from "./DropZone";

function guessKind(name: string): SourceKind {
  const n = name.toLowerCase();
  if (/pyq|past|paper|exam|question/.test(n)) return "pyq";
  if (/book|chapter|ch\d/.test(n)) return "textbook";
  if (/note/.test(n) || n.endsWith(".md") || n.endsWith(".txt")) return "notes";
  return "other";
}

function fmtSize(bytes: number): string {
  if (bytes > 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${Math.max(1, Math.round(bytes / 1024))} KB`;
}

export function SourcesShelf({ courseId }: { courseId: string }) {
  const sources = useSources(courseId);
  const upload = useUploadSource(courseId);
  const patch = usePatchSource(courseId);
  const del = useDeleteSource(courseId);
  const [err, setErr] = useState("");

  const onFiles = (files: File[]) => {
    setErr("");
    for (const f of files) {
      upload.mutate({ file: f, kind: guessKind(f.name) }, { onError: (e) => setErr(errorMessage(e)) });
    }
  };

  return (
    <section className="stack">
      <h2>Sources</h2>
      <p className="muted small">Every file for this course: slides, past papers, notes, textbook chapters.</p>
      <ul className="list">
        {sources.data?.map((s) => (
          <li key={s.id} className="list-row">
            <span className="grow truncate" title={s.filename}>{s.filename}</span>
            <span className="muted small mono">{fmtSize(s.size)}{s.slide_count ? ` · ${s.slide_count} p` : ""}</span>
            <label className="visually-hidden" htmlFor={`kind-${s.id}`}>Kind of file</label>
            <select
              id={`kind-${s.id}`}
              className="select select-sm"
              value={s.kind}
              onChange={(e) => patch.mutate({ id: s.id, kind: e.target.value as SourceKind })}
            >
              {Object.entries(SOURCE_KIND_LABEL).map(([k, v]) => (
                <option key={k} value={k}>{v}</option>
              ))}
            </select>
            {s.lecture_id ? (
              <span className="small muted">in a lecture</span>
            ) : (
              <button
                className="btn btn-ghost btn-sm"
                onClick={() => window.confirm(`Remove ${s.filename}?`) && del.mutate(s.id)}
              >
                Remove
              </button>
            )}
          </li>
        ))}
      </ul>
      <DropZone accept=".pdf,.pptx,.txt,.md" onFiles={onFiles} label="Add files" disabled={upload.isPending}>
        <span className="muted small">Drop PDFs, PPTX, TXT or MD here</span>
      </DropZone>
      {err && <p className="banner banner-error">{err}</p>}
    </section>
  );
}
