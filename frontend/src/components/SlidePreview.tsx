import { useEffect, useState } from "react";
import { thumbUrl, useSlides, useSources } from "../api/lectures";
import type { SlideRef } from "../api/types";
import { Modal } from "./Modal";

interface Props {
  courseId: string;
  refs: SlideRef[];
  start?: number;
  onClose: () => void;
}

export function SlidePreview({ courseId, refs, start = 0, onClose }: Props) {
  const [i, setI] = useState(start);
  const ref = refs[i];
  const sources = useSources(courseId);
  const slides = useSlides(courseId, ref?.source_id ?? null);
  const meta = sources.data?.find((s) => s.id === ref?.source_id);
  const slide = slides.data?.slides.find((s) => s.number === ref?.slide);
  const [imgFailed, setImgFailed] = useState(false);

  useEffect(() => setImgFailed(false), [i]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "ArrowRight") setI((x) => Math.min(refs.length - 1, x + 1));
      if (e.key === "ArrowLeft") setI((x) => Math.max(0, x - 1));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [refs.length]);

  if (!ref) return null;
  const showImage = meta?.has_thumbnails && !imgFailed;
  return (
    <Modal title={`Slide ${ref.slide}${meta ? ` · ${meta.filename}` : ""}`} onClose={onClose} wide>
      <div className="slide-view">
        {showImage ? (
          <img src={thumbUrl(courseId, ref.source_id, ref.slide)} alt={`Slide ${ref.slide}`} onError={() => setImgFailed(true)} />
        ) : (
          <pre className="slide-text">{slide ? slide.text || "(no text on this slide)" : "Loading…"}</pre>
        )}
      </div>
      {showImage && slide?.text && (
        <details>
          <summary className="small muted">Slide text</summary>
          <pre className="slide-text">{slide.text}</pre>
        </details>
      )}
      {refs.length > 1 && (
        <div className="row">
          <button className="btn btn-sm" disabled={i === 0} onClick={() => setI(i - 1)}>← Previous</button>
          <span className="spacer" />
          <span className="small muted mono">{i + 1} / {refs.length}</span>
          <span className="spacer" />
          <button className="btn btn-sm" disabled={i === refs.length - 1} onClick={() => setI(i + 1)}>Next →</button>
        </div>
      )}
    </Modal>
  );
}
