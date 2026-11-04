import { useState, type ReactNode } from "react";
import { STATUS_LABEL, type MapDoc, type SlideRef, type Status } from "../api/types";
import { nodePath } from "./mapData";
import { ThreadTab } from "./ThreadTab";

const STATUSES: Status[] = ["not_started", "confused", "revising", "got_it"];
export type PanelTab = "thread" | "notes" | "practice";

interface Props {
  courseId: string;
  lectureId: string;
  doc: MapDoc;
  nodeId: string;
  focus: boolean;
  onToggleFocus: () => void;
  onClose: () => void;
  onPreview: (refs: SlideRef[], start: number) => void;
  onStatus: (s: Status) => void;
  onTestMe?: () => void;
  onMore: (x: number, y: number) => void;
  draft: string;
  setDraft: (s: string) => void;
  notesTab?: ReactNode;
  practiceTab?: ReactNode;
  keptCount: number;
}

export function SidePanel(p: Props) {
  const node = p.doc.nodes[p.nodeId];
  const [tab, setTab] = useState<PanelTab>("thread");
  if (!node) return null;
  const path = nodePath(p.doc, node.id);

  return (
    <aside className={p.focus ? "side-panel focus" : "side-panel"} aria-label={`Topic: ${node.label}`}>
      <div className="panel-head">
        <div className="grow">
          <p className="small muted breadcrumb-path">{path.slice(0, -1).join(" › ") || "Lecture"}</p>
          <h2>{node.label}</h2>
        </div>
        <button className="btn btn-ghost btn-sm" onClick={p.onToggleFocus} aria-pressed={p.focus}>
          {p.focus ? "Collapse" : "Expand"} <span className="kbd">{p.focus ? "Esc" : "F"}</span>
        </button>
        <button className="btn btn-ghost btn-sm" onClick={p.onClose} aria-label="Close panel">✕</button>
      </div>

      {node.sources.length > 0 && (
        <div className="chips" aria-label="Source slides">
          {node.sources.map((s, i) => (
            <button key={`${s.source_id}-${s.slide}`} className="chip" onClick={() => p.onPreview(node.sources, i)}>
              Slide {s.slide}
            </button>
          ))}
        </div>
      )}

      <div className="row wrap panel-controls">
        <div className="row status-row" role="radiogroup" aria-label="Status">
          {STATUSES.map((s) => (
            <button
              key={s}
              role="radio"
              aria-checked={node.status === s}
              className={node.status === s ? "chip active" : "chip"}
              onClick={() => p.onStatus(s)}
            >
              <span className={`status-dot status-${s}`} aria-hidden="true" /> {STATUS_LABEL[s]}
            </button>
          ))}
        </div>
      </div>
      <div className="row wrap">
        {p.onTestMe && <button className="btn btn-primary btn-sm" onClick={p.onTestMe}>Test me</button>}
        <button className="btn btn-sm" onClick={(e) => p.onMore(e.clientX, e.clientY)}>Edit…</button>
      </div>

      <div className="tabs" role="tablist" aria-label="Topic sections">
        {(["thread", "notes", "practice"] as PanelTab[]).map((t) => (
          <button key={t} role="tab" aria-selected={tab === t} className={tab === t ? "tab active" : "tab"} onClick={() => setTab(t)}>
            {t === "thread" ? <>Thread {p.keptCount > 0 && <span className="badge">{p.keptCount}</span>}</> : t === "notes" ? "Notes" : "Practice"}
          </button>
        ))}
      </div>
      <div className="tab-body" role="tabpanel">
        {tab === "thread" && (
          <ThreadTab courseId={p.courseId} lectureId={p.lectureId} nodeId={node.id} nodeLabel={node.label}
            draft={p.draft} setDraft={p.setDraft} />
        )}
        {tab === "notes" && (p.notesTab ?? <p className="muted small">No notes yet.</p>)}
        {tab === "practice" && (p.practiceTab ?? <p className="muted small">No cards or saved questions yet.</p>)}
      </div>
    </aside>
  );
}
