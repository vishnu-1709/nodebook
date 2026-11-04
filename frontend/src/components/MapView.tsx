import MindElixir, { type MindElixirData, type NodeObj, type SubLineParams, type Theme } from "mind-elixir";
import "mind-elixir/style.css";
import { useEffect, useRef } from "react";
import type { MapDoc } from "../api/types";
import { ulid } from "../lib/ulid";
import { fromMindElixir, toMindElixir, treeOf, type NodeMeta, type TreeIn } from "./mapData";

export type MindInstance = MindElixir<NodeMeta>;

interface Props {
  doc: MapDoc;
  keptCounts?: Record<string, number>;
  editable?: boolean;
  selectedId?: string | null;
  onSelect?: (nodeId: string | null) => void;
  /** Called (debounced) whenever the editor's structure differs from the stored doc. */
  onStructure?: (tree: TreeIn) => void;
  onContextMenu?: (nodeId: string, x: number, y: number) => void;
  /** Return false to cancel a delete (e.g. after a confirm()). */
  confirmDelete?: (nodeIds: string[]) => boolean;
  onReady?: (me: MindInstance) => void;
  /** Double-click a node (UI: double-click or F to expand into Focus). */
  onOpen?: (nodeId: string) => void;
}

function applyData(inst: MindElixir<NodeMeta>, data: MindElixirData<NodeMeta>): void {
  if (typeof inst.diffRefresh === "function") inst.diffRefresh(data);
  else inst.refresh(data);
}

/** Fit the whole tree inside the canvas and centre it (UI.md §3.2: fit to view on load). */
export function fitToView(inst: MindElixir<NodeMeta>, pad = 24): void {
  const map = inst.map;
  const cont = inst.container;
  map.style.transformOrigin = "0 0";
  map.style.transform = "translate3d(0px, 0px, 0) scale(1)";
  const c = cont.getBoundingClientRect();
  const n = inst.nodes.getBoundingClientRect();
  if (!n.width || !n.height || !c.width || !c.height) return;
  const ox = n.left - c.left;
  const oy = n.top - c.top;
  const s = Math.max(0.2, Math.min(1, (c.width - pad) / n.width, (c.height - pad) / n.height));
  const tx = (c.width - n.width * s) / 2 - ox * s;
  const ty = (c.height - n.height * s) / 2 - oy * s;
  map.style.transform = `translate3d(${tx}px, ${ty}px, 0) scale(${s})`;
  inst.scaleVal = s;
}

/** Boxed-node connector: parent's right edge → child's left edge (no underline style). */
function subBranch(this: MindElixir, p: SubLineParams): string {
  const gap = parseInt(this.container.style.getPropertyValue("--node-gap-x")) || 0;
  const y1 = p.pT + p.pH / 2;
  const y2 = p.cT + p.cH / 2;
  if (p.direction === "lhs") {
    const x1 = p.pL + gap;
    const x2 = p.cL + p.cW - gap;
    const mid = (x1 + x2) / 2;
    return `M ${x1} ${y1} C ${mid} ${y1} ${mid} ${y2} ${x2} ${y2}`;
  }
  const x1 = p.pL + p.pW - gap;
  const x2 = p.cL + gap;
  const mid = (x1 + x2) / 2;
  return `M ${x1} ${y1} C ${mid} ${y1} ${mid} ${y2} ${x2} ${y2}`;
}

const THEME: Theme<NodeMeta> = {
  name: "Nodebook",
  palette: ["var(--line)"],
  generateSubBranch: subBranch as Theme<NodeMeta>["generateSubBranch"],
  cssVar: {
    "--node-gap-x": "24px",
    "--node-gap-y": "6px",
    "--main-gap-x": "64px",
    "--main-gap-y": "14px",
    "--root-radius": "10px",
    "--main-radius": "8px",
    "--root-color": "var(--accent-text)",
    "--root-bgcolor": "var(--accent)",
    "--root-border-color": "var(--accent)",
    "--main-color": "var(--text)",
    "--main-bgcolor": "var(--surface)",
    "--main-bgcolor-transparent": "var(--surface)",
    "--main-border": "1px solid var(--border-strong)",
    "--topic-padding": "4px 8px",
    "--color": "var(--text)",
    "--bgcolor": "var(--ground)",
    "--selected": "var(--accent)",
    "--accent-color": "var(--accent)",
    "--panel-color": "var(--text)",
    "--panel-bgcolor": "var(--surface)",
    "--panel-border-color": "var(--border)",
    "--map-padding": "40px 60px",
  },
};

export function MapView(props: Props) {
  const { doc, keptCounts, editable = false, selectedId } = props;
  const host = useRef<HTMLDivElement>(null);
  const me = useRef<MindInstance | null>(null);
  const cb = useRef(props);
  cb.current = props;
  const lastStructure = useRef<string>(JSON.stringify(treeOf(doc)));
  const fitRef = useRef<() => void>(() => {});
  const ready = useRef(false);
  const pending = useRef<MindElixirData<NodeMeta> | null>(null);

  useEffect(() => {
    if (!host.current) return;
    const el = host.current;
    const inst = new MindElixir<NodeMeta>({
      el,
      direction: MindElixir.RIGHT,
      editable,
      contextMenu: false,
      toolBar: false,
      keypress: editable,
      allowUndo: editable,
      theme: THEME,
      alignment: "root",
      newTopicName: "New topic",
      before: {
        removeNodes: (tpcs) => {
          const ids = tpcs.map((t) => t.nodeObj.id);
          return cb.current.confirmDelete ? cb.current.confirmDelete(ids) : true;
        },
      },
    });
    // our IDs are ULIDs; make Mind-Elixir create nodes with them
    inst.generateNewObj = () => ({ topic: inst.newTopicName, id: ulid() });
    const data: MindElixirData<NodeMeta> = { nodeData: toMindElixir(doc, keptCounts) };
    // fit to view on load, and again on resize until the user pans or zooms
    let userMoved = false;
    const fit = () => {
      if (me.current !== inst) return;
      fitToView(inst);
    };
    void inst.init(data).then(() => {
      ready.current = true;
      if (pending.current) {
        applyData(inst, pending.current);
        pending.current = null;
      }
      requestAnimationFrame(fit);
    });
    const ro = new ResizeObserver(() => {
      if (!userMoved) fit();
    });
    ro.observe(el);
    const markMoved = () => { userMoved = true; };
    el.addEventListener("wheel", markMoved, { passive: true });
    el.addEventListener("pointerdown", (e) => {
      if (!(e.target as HTMLElement).closest(".me-tpc")) markMoved();
    });
    fitRef.current = () => { userMoved = false; fit(); };
    const onDbl = (e: MouseEvent) => {
      const tpc = (e.target as HTMLElement).closest(".me-tpc") as (HTMLElement & { nodeObj?: NodeObj }) | null;
      if (!tpc?.nodeObj || !cb.current.onOpen) return;
      e.preventDefault();
      e.stopPropagation();
      cb.current.onOpen(tpc.nodeObj.id);
    };
    el.addEventListener("dblclick", onDbl, true);
    inst.bus.addListener("selectNodes", (nodes: NodeObj[]) => {
      const n = nodes[0];
      cb.current.onSelect?.(n ? n.id : null);
    });
    inst.bus.addListener("unselectNodes", () => cb.current.onSelect?.(null));

    let timer: number | undefined;
    const sync = () => {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => {
        const tree = fromMindElixir(inst.nodeData);
        const json = JSON.stringify(tree);
        if (json !== lastStructure.current) {
          lastStructure.current = json;
          cb.current.onStructure?.(tree);
        }
      }, 300);
    };
    if (editable) inst.bus.addListener("operation", sync);

    const onCtx = (e: MouseEvent) => {
      const tpc = (e.target as HTMLElement).closest(".me-tpc") as (HTMLElement & { nodeObj?: NodeObj }) | null;
      if (!tpc?.nodeObj) return;
      e.preventDefault();
      inst.selectNode(tpc as never);
      cb.current.onContextMenu?.(tpc.nodeObj.id, e.clientX, e.clientY);
    };
    el.addEventListener("contextmenu", onCtx);

    me.current = inst;
    cb.current.onReady?.(inst);
    return () => {
      window.clearTimeout(timer);
      ro.disconnect();
      el.removeEventListener("contextmenu", onCtx);
      el.removeEventListener("dblclick", onDbl, true);
      inst.destroy();
      me.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // apply outside changes (server responses, AI actions, status) without losing the viewport
  const sig = JSON.stringify([doc, keptCounts]);
  const lastSig = useRef(sig);
  useEffect(() => {
    if (sig === lastSig.current) return;
    lastSig.current = sig;
    const inst = me.current;
    if (!inst) return;
    lastStructure.current = JSON.stringify(treeOf(doc));
    const data = { nodeData: toMindElixir(doc, keptCounts) };
    if (!ready.current) pending.current = data;
    else applyData(inst, data);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sig]);

  useEffect(() => {
    const inst = me.current;
    if (!inst || !selectedId) return;
    try {
      const el = inst.findEle(selectedId);
      if (inst.currentNode !== el) inst.selectNode(el);
    } catch {
      /* collapsed or gone */
    }
  }, [selectedId, sig]);

  return (
    <>
      <div className="map-host" ref={host} aria-label="Mind map" />
      <div className="map-toolbar" role="toolbar" aria-label="Map view">
        <button title="Fit to screen" aria-label="Fit to screen" onClick={() => fitRef.current()}>⤢</button>
        <button title="Zoom in" aria-label="Zoom in" onClick={() => me.current && me.current.scale(Math.min(1.6, me.current.scaleVal + 0.15))}>+</button>
        <button title="Zoom out" aria-label="Zoom out" onClick={() => me.current && me.current.scale(Math.max(0.2, me.current.scaleVal - 0.15))}>−</button>
        <button title="Layout: both sides / right" aria-label="Toggle layout" onClick={() => {
          const inst = me.current;
          if (!inst) return;
          if (inst.direction === MindElixir.SIDE) inst.initRight(); else inst.initSide();
          requestAnimationFrame(() => fitRef.current());
        }}>⇆</button>
      </div>
    </>
  );
}
