import MindElixir, { type MindElixirData, type NodeObj, type Theme } from "mind-elixir";
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
}

const THEME: Theme<NodeMeta> = {
  name: "Nodebook",
  palette: ["var(--border-strong)"],
  cssVar: {
    "--node-gap-x": "28px",
    "--node-gap-y": "8px",
    "--main-gap-x": "56px",
    "--main-gap-y": "28px",
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

  useEffect(() => {
    if (!host.current) return;
    const el = host.current;
    const inst = new MindElixir<NodeMeta>({
      el,
      direction: MindElixir.RIGHT,
      editable,
      contextMenu: false,
      toolBar: true,
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
    void inst.init(data).then(() => {
      if (me.current === inst) inst.scaleFit();
    });
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
      el.removeEventListener("contextmenu", onCtx);
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
    inst.diffRefresh({ nodeData: toMindElixir(doc, keptCounts) });
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

  return <div className="map-host" ref={host} aria-label="Mind map" />;
}
