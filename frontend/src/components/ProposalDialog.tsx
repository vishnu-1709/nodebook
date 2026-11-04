import { useState } from "react";
import type { Proposal } from "../api/maps";
import { Modal } from "./Modal";

const TITLE: Record<Proposal["action"], string> = {
  expand: "Expand into subtopics",
  split: "Split this node",
  merge: "Merge with sibling",
  simplify: "Simplify label",
};

interface Props {
  proposal: Proposal;
  currentLabel: string;
  siblingLabel?: string;
  onApply: (p: Proposal) => void;
  onClose: () => void;
  applying?: boolean;
}

export function ProposalDialog({ proposal, currentLabel, siblingLabel, onApply, onClose, applying }: Props) {
  const [p, setP] = useState<Proposal>(proposal);
  const setPart = (i: number, label: string) =>
    setP({ ...p, parts: p.parts.map((x, j) => (j === i ? { ...x, label } : x)) });
  const removePart = (i: number) => setP({ ...p, parts: p.parts.filter((_, j) => j !== i) });
  const valid =
    p.action === "expand" ? p.parts.length > 0 && p.parts.every((x) => x.label.trim()) :
    p.action === "split" ? p.parts.length >= 2 && p.parts.every((x) => x.label.trim()) :
    Boolean(p.label?.trim());

  return (
    <Modal title={TITLE[p.action]} onClose={onClose}>
      <p className="muted small">
        {p.action === "expand" && <>New subtopics under “{currentLabel}”. Edit or remove any before applying.</>}
        {p.action === "split" && <>“{currentLabel}” becomes these nodes. The first keeps its questions, notes and cards.</>}
        {p.action === "merge" && <>“{currentLabel}” and “{siblingLabel}” become one node. Nothing attached to either is lost.</>}
        {p.action === "simplify" && <>Current label: “{currentLabel}”</>}
      </p>
      {(p.action === "expand" || p.action === "split") && (
        <ul className="stack proposal-list">
          {p.parts.map((part, i) => (
            <li key={i} className="row">
              <input className="input" aria-label={`Label ${i + 1}`} value={part.label} onChange={(e) => setPart(i, e.target.value)} />
              <span className="small muted mono nowrap">
                {part.sources.length ? `sl. ${part.sources.map((s) => s.slide).join(", ")}` : "no slide"}
              </span>
              {p.action === "expand" && (
                <button className="btn btn-ghost btn-sm" onClick={() => removePart(i)} aria-label={`Remove ${part.label}`}>Remove</button>
              )}
            </li>
          ))}
        </ul>
      )}
      {(p.action === "merge" || p.action === "simplify") && (
        <label className="field">
          <span>New label</span>
          <input className="input" value={p.label ?? ""} onChange={(e) => setP({ ...p, label: e.target.value })} />
        </label>
      )}
      <div className="row">
        <span className="spacer" />
        <button className="btn" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" disabled={!valid || applying} onClick={() => onApply(p)}>Apply</button>
      </div>
    </Modal>
  );
}
