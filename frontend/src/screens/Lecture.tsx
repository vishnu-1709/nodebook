import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { errorMessage } from "../api/client";
import { useCourse } from "../api/hooks";
import { lk, useGenerateMap, useLecture, useMap } from "../api/lectures";
import { useMapMutations, type NodeAction, type Proposal } from "../api/maps";
import type { MapDoc, SlideRef } from "../api/types";
import { onShortcut, useUi } from "../app/store";
import { useKeptCounts } from "../api/threads";
import { SidePanel } from "../components/SidePanel";
import { ContextMenu, type MenuItem } from "../components/ContextMenu";
import { JobProgress } from "../components/JobProgress";
import { MapView, type MindInstance } from "../components/MapView";
import { formatSlideList, siblingsOf } from "../components/mapData";
import { ProposalDialog } from "../components/ProposalDialog";
import { SlidePreview } from "../components/SlidePreview";

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
  const [selected, setSelected] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ refs: SlideRef[]; start: number } | null>(null);
  const [hideCoverage, setHideCoverage] = useState(false);
  const [menu, setMenu] = useState<{ id: string; x: number; y: number } | null>(null);
  const [proposal, setProposal] = useState<Proposal | null>(null);
  const [aiError, setAiError] = useState("");
  const me = useRef<MindInstance | null>(null);
  const [focus, setFocus] = useState(false);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const counts = useKeptCounts(courseId, lectureId, status === "ready");

  const toggleFocus = useCallback(() => {
    setFocus((f) => {
      if (!f && selected) muts.patchNode.mutate({ id: selected, studied: true });
      return !f;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);

  useEffect(
    () =>
      onShortcut((action) => {
        if (action === "expand_panel" && selected) {
          toggleFocus();
          return true;
        }
        if (action === "escape") {
          if (focus) {
            setFocus(false);
            return true;
          }
          if (selected) {
            setSelected(null);
            me.current?.clearSelection();
            return true;
          }
        }
        return false;
      }),
    [selected, focus, toggleFocus],
  );

  useEffect(() => {
    setContext({ courseId, lectureId, nodeId: selected });
  }, [courseId, lectureId, selected, setContext]);
  useEffect(() => () => setContext({ courseId: null, lectureId: null, nodeId: null }), [setContext]);

  useEffect(() => {
    if (status === "ready") void qc.invalidateQueries({ queryKey: lk.map(courseId, lectureId) });
  }, [status, courseId, lectureId, qc]);

  const doc = map.data;
  const node = selected && doc ? doc.nodes[selected] : undefined;

  const confirmDelete = useCallback(
    (ids: string[]) => {
      if (!doc) return true;
      if (ids.includes(doc.root_id)) return false;
      const withKids = ids.some((id) => (doc.nodes[id]?.children.length ?? 0) > 0);
      const names = ids.map((id) => `“${doc.nodes[id]?.label ?? ""}”`).join(", ");
      return window.confirm(
        `Delete ${names}${withKids ? " and everything under it" : ""}? Questions, notes and cards on it move to its parent.`,
      );
    },
    [doc],
  );

  const runAction = (id: string, action: NodeAction, sibling_id?: string) => {
    setAiError("");
    muts.suggest.mutate(
      { id, action, sibling_id },
      { onSuccess: setProposal, onError: (e) => setAiError(errorMessage(e)) },
    );
  };

  const el = (id: string) => {
    try {
      return me.current?.findEle(id);
    } catch {
      return undefined;
    }
  };
  const edit = {
    rename: (id: string) => { const t = el(id); if (t) void me.current?.beginEdit(t); },
    addChild: (id: string) => { const t = el(id); if (t) void me.current?.addChild(t); },
    addSibling: (id: string) => { const t = el(id); if (t) void me.current?.insertSibling("after", t); },
    remove: (id: string) => { const t = el(id); if (t) void me.current?.removeNodes([t]); },
  };

  const menuItems = (id: string, d: MapDoc): MenuItem[] => {
    const isRoot = id === d.root_id;
    const sibs = siblingsOf(d, id);
    return [
      { label: "Rename", hint: "F2", onSelect: () => edit.rename(id) },
      { label: "Add child", hint: "Tab", onSelect: () => edit.addChild(id) },
      { label: "Add sibling", hint: "Enter", onSelect: () => edit.addSibling(id), disabled: isRoot },
      { label: "Delete", hint: "Del", onSelect: () => edit.remove(id), disabled: isRoot },
      { separator: true, label: "" },
      { label: "Expand into subtopics", onSelect: () => runAction(id, "expand") },
      { label: "Split", onSelect: () => runAction(id, "split"), disabled: isRoot },
      { label: "Simplify label", onSelect: () => runAction(id, "simplify") },
      ...(isRoot ? [] : [{
        label: "Merge with sibling",
        submenu: sibs.map((s) => ({ label: s.label, onSelect: () => runAction(id, "merge", s.id) })),
      }]),
    ];
  };

  if (lecture.isError) return <div className="content"><p className="banner banner-error">{errorMessage(lecture.error)}</p></div>;
  const l = lecture.data;

  return (
    <div className="lecture-screen">
      <header className="topbar">
        <nav className="breadcrumb small" aria-label="Breadcrumb">
          <Link to={`/course/${courseId}`}>{course.data?.course.name ?? "Course"}</Link>
          <span aria-hidden="true"> › </span>
          <span>{l?.title ?? "…"}</span>
        </nav>
        <span className="spacer" />
        {muts.structure.isPending && <span className="small muted">Saving…</span>}
        {muts.suggest.isPending && <span className="small muted">Asking the model…</span>}
        {status === "ready" && (
          <button
            className="btn btn-sm"
            onClick={() => {
              if (window.confirm("Regenerate the map from the slides? Your edits to this map will be replaced.")) gen.mutate();
            }}
          >
            Regenerate map
          </button>
        )}
      </header>

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
          <div className="banner">
            <span>The model's map didn't pass the checks, so this is a simpler flat map. A larger map model usually does better.</span>
          </div>
        )}
        {status === "ready" && l && l.uncovered_slides.length > 0 && !hideCoverage && (
          <div className="banner">
            <span>
              Slide{l.uncovered_slides.length > 1 ? "s" : ""} {formatSlideList(l.uncovered_slides.map((s) => s.slide))}{" "}
              {l.uncovered_slides.length > 1 ? "aren't" : "isn't"} in the map — add {l.uncovered_slides.length > 1 ? "them" : "it"}?
            </span>
            <span className="spacer" />
            <button className="btn btn-sm" onClick={() => setPreview({ refs: l.uncovered_slides, start: 0 })}>View</button>
            <button className="btn btn-sm btn-primary" onClick={() => muts.addUncovered.mutate()} disabled={muts.addUncovered.isPending}>Add to map</button>
            <button className="btn btn-sm btn-ghost" onClick={() => setHideCoverage(true)}>Dismiss</button>
          </div>
        )}
        {aiError && (
          <div className="banner banner-error">
            <span>{aiError}</span>
            <span className="spacer" />
            <button className="btn btn-sm btn-ghost" onClick={() => setAiError("")}>Dismiss</button>
          </div>
        )}
        {muts.structure.isError && (
          <div className="banner banner-error"><span>Couldn't save that change: {errorMessage(muts.structure.error)}. The map was reloaded.</span></div>
        )}
      </div>

      <div className="lecture-body">
        <div className={focus ? "map-area hidden" : "map-area"} aria-hidden={focus}>
          {doc && (
            <MapView
              doc={doc}
              keptCounts={counts.data}
              editable
              selectedId={selected}
              onSelect={setSelected}
              onStructure={(tree) => muts.structure.mutate(tree)}
              onContextMenu={(id, x, y) => setMenu({ id, x, y })}
              confirmDelete={confirmDelete}
              onReady={(inst) => (me.current = inst)}
            />
          )}
          {status === "ready" && map.isError && <p className="banner banner-error">{errorMessage(map.error)}</p>}
        </div>
        {node && doc && (
          <SidePanel
            courseId={courseId}
            lectureId={lectureId}
            doc={doc}
            nodeId={node.id}
            focus={focus}
            onToggleFocus={toggleFocus}
            onClose={() => { setFocus(false); setSelected(null); }}
            onPreview={(refs, start) => setPreview({ refs, start })}
            onStatus={(st) => muts.patchNode.mutate({ id: node.id, status: st })}
            onMore={(x, y) => setMenu({ id: node.id, x, y })}
            draft={drafts[node.id] ?? ""}
            setDraft={(t) => setDrafts((d) => ({ ...d, [node.id]: t }))}
            keptCount={counts.data?.[node.id] ?? 0}
          />
        )}
      </div>

      {menu && doc && doc.nodes[menu.id] && (
        <ContextMenu x={menu.x} y={menu.y} items={menuItems(menu.id, doc)} onClose={() => setMenu(null)} />
      )}
      {proposal && doc && (
        <ProposalDialog
          proposal={proposal}
          currentLabel={doc.nodes[proposal.node_id]?.label ?? ""}
          siblingLabel={proposal.sibling_id ? doc.nodes[proposal.sibling_id]?.label : undefined}
          applying={muts.apply.isPending}
          onClose={() => setProposal(null)}
          onApply={(p) =>
            muts.apply.mutate(p, {
              onSuccess: () => setProposal(null),
              onError: (e) => {
                setProposal(null);
                setAiError(errorMessage(e));
              },
            })
          }
        />
      )}
      {preview && <SlidePreview courseId={courseId} refs={preview.refs} start={preview.start} onClose={() => setPreview(null)} />}
    </div>
  );
}
