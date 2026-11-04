"""Coverage check (SPEC §4 step 6): slides not referenced by any node
(the root cites the title slide)."""

from __future__ import annotations

from backend.core.schemas import MapDoc, Slide, SlideRef


def uncovered_slides(doc: MapDoc, slides: list[tuple[SlideRef, Slide]]) -> list[SlideRef]:
    referenced = {
        (s.source_id, s.slide)
        for n in doc.nodes.values()
        for s in n.sources
    }
    out = []
    for ref, slide in slides:
        if (ref.source_id, ref.slide) in referenced:
            continue
        if not slide.text.strip() and not slide.has_images:
            continue  # blank slide: nothing to cover
        out.append(ref)
    return out
