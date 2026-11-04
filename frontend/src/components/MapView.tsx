import MindElixir, { type MindElixirData, type NodeObj, type Theme } from "mind-elixir";
import "mind-elixir/style.css";
import { useEffect, useRef } from "react";
import type { MapDoc } from "../api/types";
import { toMindElixir, type NodeMeta } from "./mapData";

export type MindInstance = MindElixir<NodeMeta>;

interface Props {
  doc: MapDoc;
  keptCounts?: Record<string, number>;
  editable?: boolean;
  selectedId?: string | null;
  onSelect?: (nodeId: string | null) => void;
  /** Called once the instance exists so editing code (M3) can attach. */
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

export function MapView({ doc, keptCounts, editable = false, selectedId, onSelect, onReady }: Props) {
  const host = useRef<HTMLDivElement>(null);
  const me = useRef<MindInstance | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  // create once
  useEffect(() => {
    if (!host.current) return;
    const inst = new MindElixir<NodeMeta>({
      el: host.current,
      direction: MindElixir.RIGHT,
      editable,
      contextMenu: false,
      toolBar: true,
      keypress: editable,
      allowUndo: editable,
      theme: THEME,
      alignment: "root",
    });
    const data: MindElixirData<NodeMeta> = { nodeData: toMindElixir(doc, keptCounts) };
    void inst.init(data).then(() => {
      if (me.current === inst) inst.scaleFit();
    });
    inst.bus.addListener("selectNodes", (nodes: NodeObj[]) => {
      const n = nodes[0];
      onSelectRef.current?.(n ? n.id : null);
    });
    inst.bus.addListener("unselectNodes", () => onSelectRef.current?.(null));
    me.current = inst;
    onReady?.(inst);
    return () => {
      inst.destroy();
      me.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // re-render when the document changes (keeps viewport)
  const sig = JSON.stringify([doc, keptCounts]);
  const firstSig = useRef(sig);
  useEffect(() => {
    if (sig === firstSig.current) return;
    firstSig.current = sig;
    const inst = me.current;
    if (!inst) return;
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
  }, [selectedId]);

  return <div className="map-host" ref={host} aria-label="Mind map" />;
}
