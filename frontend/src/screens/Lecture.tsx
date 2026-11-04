import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { errorMessage } from "../api/client";
import { useCourse } from "../api/hooks";
import { lk, useGenerateMap, useLecture, useMap } from "../api/lectures";
import { useMapMutations, type NodeAction, type Proposal } from "../api/maps";
import { useKeptCounts } from "../api/threads";
import type { MapDoc, SlideRef } from "../api/types";
import { onShortcut, useUi } from "../app/store";
import { touch, usePomodoro } from "../app/pomodoro";
import { ContextMenu, type MenuItem } from "../components/ContextMenu";
import { ExplainBack } from "../components/ExplainBack";
import { JobProgress } from "../components/JobProgress";
import { LectureNotesView, LectureSourcesView } from "../components/LectureTabs";
import { MapView, type MindInstance } from "../components/MapView";
import { formatSlideList, siblingsOf } from "../components/mapData";
import { NotesTab } from "../components/NotesTab";
import { PracticeTab } from "../components/PracticeTab";
import { ProposalDialog } from "../components/ProposalDialog";
import { ScreenHeader } from "../components/ScreenHeader";
import { LectureSummary, SidePanel } from "../components/SidePanel";
import { SlidePreview } from "../components/SlidePreview";
import { TestMe } from "../components/TestMe";

type View = "map" | "sources" | "notes";

function exportOutline(doc: MapDoc): string {
  const lines: string[] = [];
  const walk = (id: string, depth: number) => {
    const n = doc.nodes[id];
    if (!n) return;
    const slides = n.sources.length ? ` (slides ${n.sources.map((s) => s.slide).join(", ")})` : "";
    lines.push(depth === 0 ? `# ${n.label}` : `${"  ".repeat(depth - 1)}- ${n.label}${slides}`);
    n.children.forEach((c) => walk(c, depth + 1));
  };
  walk(doc.root_id, 0);
  return lines.join("\n") + "\n";
}

export function LectureScreen() {
  const { courseId = "", lectureId = "" } = useParams();
  const course = useCourse(courseId);
  const lecture = useLecture(courseId, lectureId, true);
  const status = lecture.data?.map_status;
  const map = useMap(courseId, lectureId, status === "ready");
  const gen = useGenerateMap(courseId, lectureId);
  const muts = useMapMutations(courseId, lectureId);
  const qc = useQueryClient();
  const setContext = useUi((s) => s.setContext);
  const openOverlay = useUi((s) => s.open);
  const [view, setView] = useState<View>("map");
  const [search] = useSearchParams();
  const [selected, setSelected] = useState<string | null>(search.get("node"));
  const [preview, setPreview] = useState<{ refs: SlideRef[]; start: number } | null>(null);
  const [hideCoverage, setHideCoverage] = useState(false);
  const [menu, setMenu] = useState<{ id: string; x: number; y: number } | null>(null);
  const [moreMenu, setMoreMenu] = useState<{ x: number; y: number } | null>(null);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [aiError, setAiError] = useState("");
  const me = useRef<MindInstance | null>(null);
  const [focus, setFocus] = useState(false);
  const [testMe, setTestMe] = useState<string | null>(null);
  const [explain, setExplain] = useState<string | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const counts = useKeptCounts(courseId, lectureId, status === "ready");
  // results / ratings can change automatic statuses: refresh the map + reasons
  const refreshStatus = useCallback(() => {
    void qc.invalidateQueries({ queryKey: lk.map(courseId, lectureId) });
    void qc.invalidateQueries({ queryKey: ["node-status"] });
  }, [qc, courseId, lectureId]);

  const studied = useCallback((id: string) => muts.patchNode.mutate({ id, studied: true }), [muts.patchNode]);
  const [deleted, setDeleted] = useState<string[] | null>(null);
  const undoTimer = useRef<number | null>(null);
  const undoRef = useRef<{ undo: () => void; redo: () => void } | null>(null);
  const toggleFocus = useCallback(() => {
    if (!selected) return;
    if (!focus) studied(selected);
    setFocus(!focus);
  }, [selected, focus, studied]);

  useEffect(() => {
    setContext({ courseId, lectureId, nodeId: selected });
    if (selected) {
      const p = usePomodoro.getState();
      p.set(touch(p.s, { course_id: courseId, lecture_id: lectureId, node_id: selected }));
    }
  }, [courseId, lectureId, selected, setContext]);
  useEffect(() => () => setContext({ courseId: null, lectureId: null, nodeId: null }), [setContext]);
  useEffect(() => {
    if (status === "ready") void qc.invalidateQueries({ queryKey: lk.map(courseId, lectureId) });
  }, [status, courseId, lectureId, qc]);

  useEffect(
    () =>
      onShortcut((action) => {
        if (action === "expand_panel" && selected) {
          toggleFocus();
          return true;
        }
        if (action === "escape") {
          if (focus) { setFocus(false); return true; }
          if (selected) { setSelected(null); me.current?.clearSelection(); return true; }
        }
        return false;
      }),
    [selected, focus, toggleFocus],
  );

  const doc = map.data;
  const node = selected && doc ? doc.nodes[selected] : undefined;

  // No confirm dialog: deletes are undoable (toast + Ctrl/Cmd+Z). The root can't be deleted.
  const confirmDelete = useCallback((ids: string[]) => !doc || !ids.includes(doc.root_id), [doc]);

  const runAction = (id: string, action: NodeAction, sibling_id?: string) => {
    setAiError("");
    muts.suggest.mutate({ id, action, sibling_id }, { onSuccess: setProposal, onError: (e) => setAiError(errorMessage(e)) });
  };
  const withEl = (id: string, fn: (inst: MindInstance, el: ReturnType<MindInstance["findEle"]>) => void) => {
    try {
      const inst = me.current;
      if (inst) fn(inst, inst.findEle(id));
    } catch { /* collapsed or gone */ }
  };
  const removeNode = (id: string) => withEl(id, (inst, el) => void inst.removeNodes([el]));

  const menuItems = (id: string, d: MapDoc): MenuItem[] => {
    const isRoot = id === d.root_id;
    return [
      { label: "Rename", hint: "F2", onSelect: () => withEl(id, (inst, el) => void inst.beginEdit(el)) },
      { label: "Add child", hint: "Tab", onSelect: () => withEl(id, (inst, el) => void inst.addChild(el)) },
      { label: "Add sibling", hint: "Enter", disabled: isRoot, onSelect: () => withEl(id, (inst, el) => void inst.insertSibling("after", el)) },
      { separator: true, label: "" },
      { label: "AI: Expand into subtopics", onSelect: () => runAction(id, "expand") },
      { label: "AI: Split", onSelect: () => runAction(id, "split"), disabled: isRoot },
      ...(isRoot ? [] : [{ label: "AI: Merge with…", submenu: siblingsOf(d, id).map((s) => ({ label: s.label, onSelect: () => runAction(id, "merge", s.id) })) }]),
      { label: "AI: Simplify label", onSelect: () => runAction(id, "simplify") },
      { separator: true, label: "" },
      { label: "Delete", hint: "Del", onSelect: () => removeNode(id), disabled: isRoot, danger: true },
    ];
  };
  const moreItems: MenuItem[] = [
    { label: "Generate", hint: "G", onSelect: () => openOverlay("generate") },
    { label: "Quick note", hint: "N", onSelect: () => openOverlay("quick_note") },
    { label: "Regenerate map", disabled: status !== "ready", onSelect: () => {
      if (window.confirm("Regenerate the map from the slides? Your edits to this map will be replaced.")) gen.mutate();
    } },
    { label: "Export to Anki (.apkg)", onSelect: () => { window.location.href = `/api/courses/${courseId}/anki?lecture_id=${lectureId}`; } },
    { label: "Export outline (.md)", disabled: !doc, onSelect: () => {
      if (!doc) return;
      const blob = new Blob([exportOutline(doc)], { type: "text/markdown" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `${lecture.data?.title ?? "map"}.md`;
      a.click();
      URL.revokeObjectURL(a.href);
    } },
  ];

  if (lecture.isError) return <div className="content"><p className="banner banner-error">{errorMessage(lecture.error)}</p></div>;
  const l = lecture.data;
  const nNodes = doc ? Object.keys(doc.nodes).length : 0;
  const nSlides = new Set(doc ? Object.values(doc.nodes).flatMap((n) => n.sources.map((s) => `${s.source_id}:${s.slide}`)) : []).size
    + (l?.uncovered_slides.length ?? 0);

  return (
    <div className="lecture-screen">
      <ScreenHeader
        right={
          <>
            {(muts.structure.isPending || muts.suggest.isPending) && <span className="small muted">{muts.suggest.isPending ? "Asking the model…" : "Saving…"}</span>}
            <span className="hint">G generate · N note</span>
            {doc && <Link className="btn btn-sm" to={`/course/${courseId}/lecture/${lectureId}/recall`}>Recall test: rebuild this map</Link>}
            <button className="btn btn-sm" aria-label="More actions" onClick={(e) => setMoreMenu({ x: e.clientX - 200, y: e.clientY + 12 })}>⋯</button>
          </>
        }
      >
        <Link to={`/course/${courseId}`} className="back-link">← {course.data?.course.name ?? "Course"}</Link>
        <span className="lecture-title">{l?.title ?? "…"}</span>
        <div className="seg-tabs" role="tablist" aria-label="Lecture view">
          {(["map", "sources", "notes"] as View[]).map((v) => (
            <button key={v} role="tab" aria-selected={view === v} onClick={() => setView(v)}>
              {v === "map" ? "Map" : v === "sources" ? "Sources" : "Notes"}
            </button>
          ))}
        </div>
      </ScreenHeader>

      <div className="lecture-body">
        {view === "map" && (
          <div className="map-wrap">
            <div className="map-meta">
              <span>Click a node to open it · F to expand · double-click to rename</span>
              <span className="spacer" />
              {doc && <span className="mono">{nNodes} nodes · from {nSlides} slides</span>}
            </div>
            <div className="banners">
              {(status === "queued" || status === "running") && (
                <div className="banner">
                  <span>Building the map from your slides. You can keep using the app.</span>
                  <span className="spacer" />
                  <JobProgress jobId={l?.map_job_id ?? null} fallbackText="Starting…" />
                </div>
              )}
              {status === "failed" && (
                <div className="banner banner-error">
                  <span>Map generation failed: {l?.map_error}</span>
                  <span className="spacer" />
                  <button className="btn btn-sm" onClick={() => gen.mutate()}>Retry</button>
                </div>
              )}
              {status === "ready" && l?.map_fallback && (
                <div className="banner"><span>The model's map didn't pass the checks, so this is a simpler flat map. A larger map model usually does better.</span></div>
              )}
              {status === "ready" && l && l.uncovered_slides.length > 0 && !hideCoverage && (
                <div className="banner">
                  <span className="grow">
                    Slide{l.uncovered_slides.length > 1 ? "s" : ""} {formatSlideList(l.uncovered_slides.map((s) => s.slide))}{" "}
                    {l.uncovered_slides.length > 1 ? "aren't" : "isn't"} in the map — add {l.uncovered_slides.length > 1 ? "them" : "it"}?
                  </span>
                  <button className="btn btn-sm" onClick={() => setPreview({ refs: l.uncovered_slides, start: 0 })}>View</button>
                  <button className="btn btn-sm btn-primary" onClick={() => muts.addUncovered.mutate()} disabled={muts.addUncovered.isPending}>Add to map</button>
                  <button className="link-muted" onClick={() => setHideCoverage(true)}>Dismiss</button>
                </div>
              )}
              {aiError && (
                <div className="banner banner-error">
                  <span className="grow">{aiError}</span>
                  <button className="link-muted" onClick={() => setAiError("")}>Dismiss</button>
                </div>
              )}
              {muts.structure.isError && (
                <div className="banner banner-error"><span>Couldn't save that change: {errorMessage(muts.structure.error)}. The map was reloaded.</span></div>
              )}
            </div>
            <div className="map-frame" aria-hidden={focus}>
              {doc && (
                <MapView
                  doc={doc}
                  keptCounts={counts.data}
                  editable
                  selectedId={selected}
                  onSelect={setSelected}
                  onDeleted={(labels) => {
                    if (undoTimer.current) window.clearTimeout(undoTimer.current);
                    setDeleted(labels);
                    undoTimer.current = window.setTimeout(() => setDeleted(null), 6000);
                  }}
                  undoRef={undoRef}
                  onStructure={(tree) => muts.structure.mutate(tree)}
                  onContextMenu={(id, x, y) => setMenu({ id, x, y })}
                  confirmDelete={confirmDelete}
                  onReady={(inst) => (me.current = inst)}
                />
              )}
              {status === "ready" && map.isError && <p className="banner banner-error">{errorMessage(map.error)}</p>}
            </div>
            <div className="map-hints">
              <span>Tab child · Enter sibling · Del delete</span>
              <span>Right-click: AI Expand · Split · Merge · Simplify</span>
              <span>Drag to move · Ctrl/Cmd+Z undo</span>
            </div>
          </div>
        )}
        {view === "sources" && l && <LectureSourcesView courseId={courseId} lecture={l} onPreview={(refs, start) => setPreview({ refs, start })} />}
        {view === "notes" && doc && <LectureNotesView courseId={courseId} lectureId={lectureId} doc={doc} />}

        {node && doc ? (
          <SidePanel
            courseId={courseId}
            lectureId={lectureId}
            doc={doc}
            nodeId={node.id}
            focus={focus}
            onToggleFocus={toggleFocus}
            onPreview={(refs, start) => setPreview({ refs, start })}
            onStatus={(st) => muts.patchNode.mutate({ id: node.id, status: st }, { onSuccess: refreshStatus })}
            draft={drafts[node.id] ?? ""}
            setDraft={(t) => setDrafts((d) => ({ ...d, [node.id]: t }))}
            keptCount={counts.data?.[node.id] ?? 0}
            onTestMe={() => setTestMe(node.id)}
            onExplain={() => setExplain(node.id)}
            onAuto={() => muts.patchNode.mutate({ id: node.id, status_mode: "auto" }, { onSuccess: refreshStatus })}
            notesTab={<NotesTab courseId={courseId} lectureId={lectureId} nodeId={node.id} />}
            practiceTab={<PracticeTab courseId={courseId} lectureId={lectureId} nodeId={node.id} />}
          />
        ) : (
          doc && <LectureSummary doc={doc} uncovered={l?.uncovered_slides.length ?? 0} onShowUncovered={() => l && setPreview({ refs: l.uncovered_slides, start: 0 })} />
        )}
      </div>

      {deleted && (
        <div className="app-toast row" role="status">
          <span>Deleted {deleted.length === 1 ? `“${deleted[0]}”` : `${deleted.length} nodes`}.</span>
          <button className="btn btn-sm undo-btn" onClick={() => { undoRef.current?.undo(); setDeleted(null); }}>Undo</button>
        </div>
      )}
      {menu && doc && doc.nodes[menu.id] && <ContextMenu x={menu.x} y={menu.y} items={menuItems(menu.id, doc)} onClose={() => setMenu(null)} />}
      {moreMenu && <ContextMenu x={moreMenu.x} y={moreMenu.y} items={moreItems} onClose={() => setMoreMenu(null)} />}
      {proposal && doc && (
        <ProposalDialog
          proposal={proposal}
          doc={doc}
          applying={muts.apply.isPending}
          onClose={() => setProposal(null)}
          onApply={(p) =>
            muts.apply.mutate(p, {
              onSuccess: () => setProposal(null),
              onError: (e) => { setProposal(null); setAiError(errorMessage(e)); },
            })
          }
        />
      )}
      {testMe && doc?.nodes[testMe] && (
        <TestMe courseId={courseId} lectureId={lectureId} nodeId={testMe} nodeLabel={doc.nodes[testMe]!.label}
          onClose={() => { setTestMe(null); refreshStatus(); }} onPreview={(refs, start) => setPreview({ refs, start })} />
      )}
      {explain && doc?.nodes[explain] && (
        <ExplainBack courseId={courseId} lectureId={lectureId} nodeId={explain} nodeLabel={doc.nodes[explain]!.label}
          onClose={() => { setExplain(null); refreshStatus(); }} onPreview={(refs, start) => setPreview({ refs, start })} />
      )}
      {preview && <SlidePreview courseId={courseId} refs={preview.refs} start={preview.start} onClose={() => setPreview(null)} />}
    </div>
  );
}
