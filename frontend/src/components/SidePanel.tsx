import { useState, type ReactNode } from "react";
import { useLectureNotes } from "../api/notes";
import { useNodePractice } from "../api/testme";
import type { MapDoc, SlideRef, Status } from "../api/types";
import { nodePath } from "./mapData";
import { PomodoroChip } from "./PomodoroChip";
import { ThreadTab } from "./ThreadTab";

export type PanelTab = "thread" | "notes" | "practice";
const SEG: { s: Status; label: string }[] = [
  { s: "confused", label: "Confused" },
  { s: "revising", label: "Revising" },
  { s: "got_it", label: "Got it" },
];

interface Props {
  courseId: string;
  lectureId: string;
  doc: MapDoc;
  nodeId: string;
  focus: boolean;
  onToggleFocus: () => void;
  onPreview: (refs: SlideRef[], start: number) => void;
  onStatus: (s: Status) => void;
  onTestMe: () => void;
  onExplain: () => void;
  draft: string;
  setDraft: (s: string) => void;
  notesTab: ReactNode;
  practiceTab: ReactNode;
  keptCount: number;
}

export function slideRange(refs: SlideRef[]): string {
  const n = refs.map((r) => r.slide).sort((a, b) => a - b);
  if (n.length === 0) return "";
  return n.length === 1 ? `slide ${n[0]}` : `slides ${n[0]}–${n[n.length - 1]}`;
}

export function StatusSeg({ value, onChange }: { value: Status; onChange: (s: Status) => void }) {
  return (
    <div className="status-seg" role="radiogroup" aria-label="Status">
      {SEG.map(({ s, label }) => (
        <button
          key={s}
          role="radio"
          aria-checked={value === s}
          className={`s-${s}`}
          onClick={() => onChange(value === s ? "not_started" : s)}
          title={value === s ? "Click again to clear" : undefined}
        >
          {label}
        </button>
      ))}
    </div>
  );
}

export function SidePanel(p: Props) {
  const node = p.doc.nodes[p.nodeId];
  const [tab, setTab] = useState<PanelTab>("thread");
  const notes = useLectureNotes(p.courseId, p.lectureId, p.nodeId);
  const practice = useNodePractice(p.courseId, p.lectureId, p.nodeId);
  if (!node) return null;
  const path = nodePath(p.doc, node.id);
  const crumbs = path.slice(0, -1).join(" › ") || "Lecture";
  const chips = node.sources.map((s, i) => (
    <button key={`${s.source_id}-${s.slide}`} className="slide-chip" onClick={() => p.onPreview(node.sources, i)}>
      Slide {s.slide}
    </button>
  ));

  return (
    <aside className={p.focus ? "side-panel focus" : "side-panel"} aria-label={`Topic: ${node.label}`}>
      {p.focus && (
        <header className="focus-head">
          <button className="btn btn-ghost btn-sm" onClick={p.onToggleFocus}>↙ Collapse to map + panel</button>
          <span className="focus-crumbs small">{path.slice(0, -1).join(" › ")}{path.length > 1 ? " › " : ""}<strong>{node.label}</strong></span>
          <span className="row focus-head-right"><PomodoroChip /><span className="hint">Esc to exit</span></span>
        </header>
      )}
      <div className="panel-body">
        {!p.focus && (
          <div className="panel-head">
            <div className="grow">
              <p className="small muted">{crumbs}</p>
              <h2 className="panel-title">{node.label}</h2>
            </div>
            <button className="btn btn-sm" onClick={p.onToggleFocus} aria-pressed={false}>⤢ Expand <span className="kbd">F</span></button>
          </div>
        )}
        {!p.focus && (
          <div className="row panel-slides">
            <div className="chips grow">{chips}</div>
            <button className="btn btn-dark btn-sm" onClick={p.onTestMe}>Test me · 3 Qs</button>
          </div>
        )}
        {!p.focus && <StatusSeg value={node.status} onChange={p.onStatus} />}
        {!p.focus && <button className="link-btn explain-link" onClick={p.onExplain}>Explain it back in your own words →</button>}

        {p.focus && (
          <div className="focus-title-row">
            <div className="grow">
              <h1 className="focus-title">{node.label}</h1>
              <div className="chips">{chips}</div>
            </div>
            <div className="focus-status"><StatusSeg value={node.status} onChange={p.onStatus} /></div>
          </div>
        )}
        {p.focus && (
          <div className="test-card">
            <div className="grow">
              <p className="test-card-title">Test yourself on this topic</p>
              <p className="test-card-sub small">3 recall questions from {slideRange(node.sources) || "this topic"} · about 2 min</p>
            </div>
            <button className="btn btn-ghost test-card-alt" onClick={p.onExplain}>Explain it back</button>
            <button className="btn test-card-btn" onClick={p.onTestMe}>Test me</button>
          </div>
        )}

        <div className="tabs" role="tablist" aria-label="Topic sections">
          {(["thread", "notes", "practice"] as PanelTab[]).map((t) => {
            const n = t === "thread" ? p.keptCount : t === "notes" ? notes.data?.length ?? 0 : practice.data?.length ?? 0;
            const name = t === "thread" ? "Thread" : t === "notes" ? "Notes" : "Practice";
            return (
              <button key={t} role="tab" aria-selected={tab === t} className="tab" onClick={() => setTab(t)}>
                {name}{n > 0 ? ` · ${n}` : ""}
              </button>
            );
          })}
        </div>
        <div className="tab-body" role="tabpanel">
          {tab === "thread" && (
            <ThreadTab courseId={p.courseId} lectureId={p.lectureId} nodeId={node.id} nodeLabel={node.label}
              draft={p.draft} setDraft={p.setDraft} />
          )}
          {tab === "notes" && p.notesTab}
          {tab === "practice" && p.practiceTab}
        </div>
      </div>
    </aside>
  );
}

/** Shown when no node is selected (UI.md §3.2). */
export function LectureSummary({ doc, uncovered, onShowUncovered }: { doc: MapDoc; uncovered: number; onShowUncovered: () => void }) {
  const counts: Record<Status, number> = { got_it: 0, revising: 0, confused: 0, not_started: 0 };
  for (const n of Object.values(doc.nodes)) if (n.id !== doc.root_id) counts[n.status] += 1;
  const rows: { s: Status; label: string }[] = [
    { s: "got_it", label: "Got it" }, { s: "revising", label: "Revising" },
    { s: "confused", label: "Confused" }, { s: "not_started", label: "Not started" },
  ];
  return (
    <aside className="side-panel" aria-label="Lecture summary">
      <div className="panel-body">
        <p className="small muted">Lecture</p>
        <h2 className="panel-title">{doc.nodes[doc.root_id]?.label}</h2>
        <ul className="summary-list">
          {rows.map((r) => (
            <li key={r.s} className="row">
              <span className={`status-dot status-${r.s}`} aria-hidden="true" />
              <span className="grow">{r.label}</span>
              <span className="mono">{counts[r.s]}</span>
            </li>
          ))}
        </ul>
        {uncovered > 0 && (
          <button className="link-btn" onClick={onShowUncovered}>{uncovered} slide{uncovered > 1 ? "s" : ""} not in the map</button>
        )}
        <p className="muted">Click a node to start.</p>
      </div>
    </aside>
  );
}
