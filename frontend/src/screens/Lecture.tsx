import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import { errorMessage } from "../api/client";
import { useCourse } from "../api/hooks";
import { lk, useGenerateMap, useLecture, useMap } from "../api/lectures";
import { STATUS_LABEL, type SlideRef } from "../api/types";
import { useUi } from "../app/store";
import { JobProgress } from "../components/JobProgress";
import { MapView } from "../components/MapView";
import { formatSlideList, nodePath } from "../components/mapData";
import { SlidePreview } from "../components/SlidePreview";

export function LectureScreen() {
  const { courseId = "", lectureId = "" } = useParams();
  const course = useCourse(courseId);
  const lecture = useLecture(courseId, lectureId, true);
  const status = lecture.data?.map_status;
  const map = useMap(courseId, lectureId, status === "ready");
  const gen = useGenerateMap(courseId, lectureId);
  const qc = useQueryClient();
  const setContext = useUi((s) => s.setContext);
  const [selected, setSelected] = useState<string | null>(null);
  const [preview, setPreview] = useState<{ refs: SlideRef[]; start: number } | null>(null);
  const [hideCoverage, setHideCoverage] = useState(false);

  useEffect(() => {
    setContext({ courseId, lectureId, nodeId: selected });
  }, [courseId, lectureId, selected, setContext]);
  useEffect(() => () => setContext({ courseId: null, lectureId: null, nodeId: null }), [setContext]);

  useEffect(() => {
    if (status === "ready") void qc.invalidateQueries({ queryKey: lk.map(courseId, lectureId) });
  }, [status, courseId, lectureId, qc]);

  const node = selected && map.data ? map.data.nodes[selected] : undefined;
  const path = useMemo(() => (node && map.data ? nodePath(map.data, node.id) : []), [node, map.data]);

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
              {l.uncovered_slides.length > 1 ? "aren't" : "isn't"} in the map.
            </span>
            <span className="spacer" />
            <button className="btn btn-sm" onClick={() => setPreview({ refs: l.uncovered_slides, start: 0 })}>View slides</button>
            <button className="btn btn-sm btn-ghost" onClick={() => setHideCoverage(true)}>Dismiss</button>
          </div>
        )}
      </div>

      <div className="lecture-body">
        <div className="map-area">
          {map.data && <MapView doc={map.data} selectedId={selected} onSelect={setSelected} />}
          {status === "ready" && map.isError && <p className="banner banner-error">{errorMessage(map.error)}</p>}
        </div>
        {node && (
          <aside className="side-panel" aria-label="Node">
            <p className="small muted">{path.slice(0, -1).join(" › ")}</p>
            <h2>{node.label}</h2>
            <p className="row small">
              <span className={`status-dot status-${node.status}`} aria-hidden="true" /> {STATUS_LABEL[node.status]}
            </p>
            <div className="chips">
              {node.sources.map((s, i) => (
                <button key={`${s.source_id}-${s.slide}`} className="chip" onClick={() => setPreview({ refs: node.sources, start: i })}>
                  Slide {s.slide}
                </button>
              ))}
            </div>
          </aside>
        )}
      </div>
      {preview && <SlidePreview courseId={courseId} refs={preview.refs} start={preview.start} onClose={() => setPreview(null)} />}
    </div>
  );
}
