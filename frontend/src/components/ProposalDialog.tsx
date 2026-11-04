import { useState } from "react";
import type { Proposal } from "../api/maps";
import type { MapDoc } from "../api/types";
import { Modal } from "./Modal";

const TITLE: Record<Proposal["action"], string> = {
  expand: "Expand into subtopics",
  split: "Split this node",
  merge: "Merge with sibling",
  simplify: "Simplify label",
};

interface Props {
  proposal: Proposal;
  doc: MapDoc;
  onApply: (p: Proposal) => void;
  onClose: () => void;
  applying?: boolean;
}

/** Preview diff (UI.md §3.2): new nodes in green, removed/renamed struck through. Labels editable. */
export function ProposalDialog({ proposal, doc, onApply, onClose, applying }: Props) {
  const [p, setP] = useState<Proposal>(proposal);
  const node = doc.nodes[p.node_id];
  const sib = p.sibling_id ? doc.nodes[p.sibling_id] : undefined;
  const setPart = (i: number, label: string) => setP({ ...p, parts: p.parts.map((x, j) => (j === i ? { ...x, label } : x)) });
  const removePart = (i: number) => setP({ ...p, parts: p.parts.filter((_, j) => j !== i) });
  const valid =
    p.action === "expand" ? p.parts.length > 0 && p.parts.every((x) => x.label.trim()) :
    p.action === "split" ? p.parts.length >= 2 && p.parts.every((x) => x.label.trim()) :
    Boolean(p.label?.trim());
  const parts = (removable: boolean) => p.parts.map((part, i) => (
    <li key={i} className="diff-row diff-new">
      <span className="diff-sign" aria-hidden="true">+</span>
      <input className="input diff-input" aria-label={`New node ${i + 1}`} value={part.label} onChange={(e) => setPart(i, e.target.value)} />
      <span className="xsmall muted mono nowrap">{part.sources.length ? `sl. ${part.sources.map((s) => s.slide).join(", ")}` : ""}</span>
      {removable && <button className="btn btn-ghost btn-sm" onClick={() => removePart(i)} aria-label={`Remove ${part.label}`}>✕</button>}
    </li>
  ));

  return (
    <Modal title={TITLE[p.action]} onClose={onClose}>
      <ul className="diff">
        {p.action === "expand" && node && (
          <>
            <li className="diff-row diff-keep"><span className="diff-sign" /> <strong>{node.label}</strong></li>
            <li><ul className="diff diff-indent">
              {node.children.map((c) => doc.nodes[c] && <li key={c} className="diff-row diff-keep"><span className="diff-sign" />{doc.nodes[c]!.label}</li>)}
              {parts(true)}
            </ul></li>
          </>
        )}
        {p.action === "split" && node && (
          <>
            <li className="diff-row diff-old"><span className="diff-sign" aria-hidden="true">−</span><s>{node.label}</s></li>
            {parts(false)}
          </>
        )}
        {(p.action === "merge" || p.action === "simplify") && node && (
          <>
            <li className="diff-row diff-old"><span className="diff-sign" aria-hidden="true">−</span><s>{node.label}</s></li>
            {sib && <li className="diff-row diff-old"><span className="diff-sign" aria-hidden="true">−</span><s>{sib.label}</s></li>}
            <li className="diff-row diff-new">
              <span className="diff-sign" aria-hidden="true">+</span>
              <input className="input diff-input" aria-label="New label" value={p.label ?? ""} onChange={(e) => setP({ ...p, label: e.target.value })} />
            </li>
          </>
        )}
      </ul>
      <p className="small muted">
        {p.action === "split" ? "The first part keeps this node's questions, notes and cards." :
          p.action === "merge" ? "Nothing attached to either node is lost." : "You can edit any label before applying."}
      </p>
      <div className="row">
        <span className="spacer" />
        <button className="btn" onClick={onClose}>Cancel</button>
        <button className="btn btn-primary" disabled={!valid || applying} onClick={() => onApply(p)}>Apply</button>
      </div>
    </Modal>
  );
}
