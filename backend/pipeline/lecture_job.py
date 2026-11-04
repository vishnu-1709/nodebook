"""Background job: extract a lecture's sources and (re)build its map."""

from __future__ import annotations

from typing import Any

from backend.core.context import AppContext
from backend.core.courses import get_lecture, get_source, update_lecture
from backend.core.jobs import JobContext, JobInfo
from backend.core.schemas import SlideRef
from backend.core.storage import Storage
from backend.llm.base import LLMError
from backend.pipeline.extract import extract_source
from backend.pipeline.map_builder import BuildInput, DeckSlide, MapBuilder


def load_deck(st: Storage, course_id: str, source_ids: list[str]) -> list[DeckSlide]:
    deck: list[DeckSlide] = []
    for sid in source_ids:
        meta = get_source(st, course_id, sid)
        doc = extract_source(st, course_id, meta)
        deck.extend(DeckSlide(SlideRef(source_id=sid, slide=s.number), s) for s in doc.slides)
    return deck


def _model_has_vision(ctx: AppContext, model: str) -> bool:
    try:
        return any(m.name == model and m.vision for m in ctx.provider.list_models())
    except LLMError:
        return False


def start_map_job(ctx: AppContext, course_id: str, lecture_id: str) -> JobInfo:
    st = ctx.storage
    provider = ctx.provider
    lecture = get_lecture(st, course_id, lecture_id)

    def run(job: JobContext) -> dict[str, Any]:
        update_lecture(st, course_id, lecture_id, map_status="running", map_error=None)
        job.report("extract", 0.02, "Reading slides")
        deck: list[DeckSlide] = []
        n_src = max(len(lecture.source_ids), 1)
        for i, sid in enumerate(lecture.source_ids):
            meta = get_source(st, course_id, sid)

            def on_page(p: int, total: int, i: int = i) -> None:
                job.report("extract", 0.02 + 0.08 * (i + p / max(total, 1)) / n_src, f"Reading slide {p} of {total}")

            doc = extract_source(st, course_id, meta, on_page=on_page)
            deck.extend(DeckSlide(SlideRef(source_id=sid, slide=s.number), s) for s in doc.slides)

        model = ctx.require_model("map")
        vision = _model_has_vision(ctx, model)

        def image_for(ref: SlideRef) -> bytes | None:
            p = st.paths.thumbnail(course_id, ref.source_id, ref.slide)
            return st.read_bytes(p) if st.exists(p) else None

        builder = MapBuilder(provider, ctx.prompts)
        result = builder.build(
            BuildInput(lecture_id=lecture_id, lecture_title=lecture.title, slides=deck, model=model,
                       vision=vision, image_for=image_for),
            progress=lambda step, prog, msg: job.report(step, prog, msg),
        )
        st.write_doc(st.paths.map(course_id, lecture_id), result.map)
        update_lecture(
            st, course_id, lecture_id, map_status="ready", map_error=None, map_fallback=result.fallback,
            map_warnings=result.warnings, uncovered_slides=result.uncovered,
        )
        return {"nodes": len(result.map.nodes), "uncovered": len(result.uncovered), "fallback": result.fallback}

    def on_error(msg: str) -> None:
        update_lecture(st, course_id, lecture_id, map_status="failed", map_error=msg)

    update_lecture(st, course_id, lecture_id, map_status="queued", map_error=None)
    info = ctx.jobs.submit("map", run, on_error=on_error)
    update_lecture(st, course_id, lecture_id, map_job_id=info.id)
    return info
