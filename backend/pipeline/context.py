"""Slide context for prompts: the text of a node's source slides."""

from __future__ import annotations

from dataclasses import dataclass

from backend.core.courses import get_source
from backend.core.schemas import MapDoc, SlideRef
from backend.core.storage import Storage
from backend.pipeline.extract import extract_source

SLIDE_CHARS = 1500


@dataclass
class SlideText:
    ref: SlideRef
    text: str


def slide_texts(st: Storage, course_id: str, refs: list[SlideRef]) -> list[SlideText]:
    out: list[SlideText] = []
    cache: dict[str, dict[int, str]] = {}
    for r in refs:
        if r.source_id not in cache:
            try:
                meta = get_source(st, course_id, r.source_id)
                doc = extract_source(st, course_id, meta)
                cache[r.source_id] = {s.number: s.text for s in doc.slides}
            except Exception:  # noqa: BLE001 - a missing source must not break the feature
                cache[r.source_id] = {}
        text = cache[r.source_id].get(r.slide, "")
        out.append(SlideText(ref=r, text=text[:SLIDE_CHARS]))
    return out


def format_slide_texts(items: list[SlideText]) -> str:
    if not items:
        return "(no slides are linked to this topic)"
    return "\n\n".join(f"[Slide {it.ref.slide}]\n{it.text.strip() or '(no text on this slide)'}" for it in items)


def node_path(doc: MapDoc, node_id: str) -> list[str]:
    out: list[str] = []
    cur = doc.nodes.get(node_id)
    seen: set[str] = set()
    while cur is not None and cur.id not in seen:
        seen.add(cur.id)
        out.insert(0, cur.label)
        cur = doc.nodes.get(cur.parent_id) if cur.parent_id else None
    return out


def refs_for_numbers(numbers: list[int], allowed: list[SlideRef]) -> list[SlideRef]:
    """Map slide numbers in a model answer back to the node's real slide refs."""
    by_num: dict[int, SlideRef] = {}
    for r in allowed:
        by_num.setdefault(r.slide, r)
    out: list[SlideRef] = []
    for n in numbers:
        r = by_num.get(n)
        if r is not None and r not in out:
            out.append(r)
    return out
