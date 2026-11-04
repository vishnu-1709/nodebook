import { thumbUrl, useSlides, useSources } from "../api/lectures";
import { useLectureNotes } from "../api/notes";
import type { Lecture, MapDoc, SlideRef } from "../api/types";

/** Lecture header tab "Sources": the lecture's decks as a slide grid. */
export function LectureSourcesView({ courseId, lecture, onPreview }: {
  courseId: string; lecture: Lecture; onPreview: (refs: SlideRef[], start: number) => void;
}) {
  const sources = useSources(courseId);
  return (
    <div className="lecture-tab-view">
      {lecture.source_ids.map((sid) => {
        const meta = sources.data?.find((s) => s.id === sid);
        return <SourceGrid key={sid} courseId={courseId} sourceId={sid} name={meta?.filename ?? "…"} thumbs={Boolean(meta?.has_thumbnails)} onPreview={onPreview} />;
      })}
    </div>
  );
}

function SourceGrid({ courseId, sourceId, name, thumbs, onPreview }: {
  courseId: string; sourceId: string; name: string; thumbs: boolean; onPreview: (refs: SlideRef[], start: number) => void;
}) {
  const slides = useSlides(courseId, sourceId);
  const refs = (slides.data?.slides ?? []).map((s) => ({ source_id: sourceId, slide: s.number }));
  return (
    <section className="stack">
      <h2>{name} <span className="muted mono small">{refs.length} slides</span></h2>
      <div className="slide-grid">
        {slides.data?.slides.map((s, i) => (
          <button key={s.number} className="slide-tile" onClick={() => onPreview(refs, i)} aria-label={`Slide ${s.number}`}>
            {thumbs ? <img src={thumbUrl(courseId, sourceId, s.number)} alt="" loading="lazy" /> : <span className="slide-tile-text">{s.text.slice(0, 120) || "(no text)"}</span>}
            <span className="mono xsmall muted">{s.number}</span>
          </button>
        ))}
      </div>
    </section>
  );
}

/** Lecture header tab "Notes": every note in this lecture, grouped by topic. */
export function LectureNotesView({ courseId, lectureId, doc }: { courseId: string; lectureId: string; doc: MapDoc }) {
  const notes = useLectureNotes(courseId, lectureId);
  const groups = new Map<string, typeof notes.data>();
  for (const n of notes.data ?? []) {
    const key = n.node_id && doc.nodes[n.node_id] ? n.node_id : "";
    groups.set(key, [...(groups.get(key) ?? []), n]);
  }
  return (
    <div className="lecture-tab-view">
      {notes.data?.length === 0 && <p className="muted">No notes in this lecture yet. Press N to add one.</p>}
      {[...groups.entries()].map(([key, items]) => (
        <section key={key} className="stack">
          <h2>{key ? doc.nodes[key]!.label : "Lecture notes"}</h2>
          <ul className="note-list">
            {items?.map((n) => <li key={n.id} className="note"><p className="note-text">{n.text}</p></li>)}
          </ul>
        </section>
      ))}
    </div>
  );
}
