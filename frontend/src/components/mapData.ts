import type { NodeObj } from "mind-elixir";
import type { MapDoc, Status } from "../api/types";
import { STATUS_LABEL } from "../api/types";

export interface NodeMeta {
  status: Status;
}

/** MapDoc (our IDs, flat dict) → Mind-Elixir tree. IDs are preserved 1:1. */
export function toMindElixir(doc: MapDoc, keptCounts: Record<string, number> = {}): NodeObj<NodeMeta> {
  const seen = new Set<string>();
  const build = (id: string): NodeObj<NodeMeta> => {
    const n = doc.nodes[id];
    if (!n) throw new Error(`map node ${id} missing`);
    seen.add(id);
    const tags: { text: string; className: string }[] = [
      {
        text: n.status === "not_started" ? "" : STATUS_LABEL[n.status],
        className: `me-status status-${n.status}`,
      },
    ];
    const kept = keptCounts[id] ?? 0;
    if (kept > 0) tags.push({ text: String(kept), className: "me-badge" });
    return {
      id: n.id,
      topic: n.label,
      expanded: !n.collapsed,
      tags: id === doc.root_id ? [] : tags,
      metadata: { status: n.status },
      children: n.children.filter((c) => doc.nodes[c] && !seen.has(c)).map(build),
    };
  };
  return build(doc.root_id);
}

export function nodePath(doc: MapDoc, id: string): string[] {
  const out: string[] = [];
  let cur = doc.nodes[id];
  const guard = new Set<string>();
  while (cur && !guard.has(cur.id)) {
    guard.add(cur.id);
    out.unshift(cur.label);
    cur = cur.parent_id ? doc.nodes[cur.parent_id] : undefined;
  }
  return out;
}

export function formatSlideList(slides: number[]): string {
  const s = [...slides].sort((a, b) => a - b);
  if (s.length <= 1) return s.join("");
  return `${s.slice(0, -1).join(", ")} and ${s[s.length - 1]}`;
}

export interface TreeIn {
  id: string;
  label: string;
  collapsed: boolean;
  children: TreeIn[];
}

/** Mind-Elixir tree → structure payload for PUT /map/structure. */
export function fromMindElixir(n: NodeObj): TreeIn {
  return {
    id: n.id,
    label: n.topic,
    collapsed: n.expanded === false,
    children: (n.children ?? []).map(fromMindElixir),
  };
}

/** Same shape built from our stored doc (for change detection). */
export function treeOf(doc: MapDoc, id: string = doc.root_id): TreeIn {
  const n = doc.nodes[id]!;
  return {
    id,
    label: n.label,
    collapsed: n.collapsed,
    children: n.children.filter((c) => doc.nodes[c]).map((c) => treeOf(doc, c)),
  };
}

export function siblingsOf(doc: MapDoc, id: string): { id: string; label: string }[] {
  const n = doc.nodes[id];
  if (!n?.parent_id) return [];
  const p = doc.nodes[n.parent_id];
  return (p?.children ?? []).filter((c) => c !== id && doc.nodes[c]).map((c) => ({ id: c, label: doc.nodes[c]!.label }));
}
