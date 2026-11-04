"""Generate panel (SPEC §5.8): one item at a time from chosen sources."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from backend.core.courses import get_lecture, get_source, list_lectures
from backend.core.schemas import MapDoc, NoteDestination, SlideRef
from backend.core.storage import Storage
from backend.llm.base import ChatMessage, LLMError, LLMProvider
from backend.llm.prompts import PromptLibrary
from backend.pipeline.extract import extract_source

GenType = Literal["questions", "flashcards", "summary", "explain"]
Chip = Literal["harder", "easier", "conceptual", "numerical"]
MAX_CHARS = 14000
CHIP_TEXT = {
    "harder": "Make it harder than a typical exam question on this.",
    "easier": "Make it easier: a warm-up a beginner can answer.",
    "conceptual": "Focus on concepts and reasoning, not calculation.",
    "numerical": "Make it a numerical problem with concrete numbers (only if the sources support it).",
}


class Cite(BaseModel):
    source: int
    page: int


class GenOut(BaseModel):
    front: str = ""
    back: str = ""
    title: str = ""
    body: str = ""
    cites: list[Cite] = Field(default_factory=list)
    ref: str = ""


class GenRequest(BaseModel):
    type: GenType
    source_ids: list[str] = Field(default_factory=list)
    lecture_ids: list[str] = Field(default_factory=list)
    steer: str = Field(default="", max_length=500)
    chips: list[Chip] = Field(default_factory=list)
    topic: str = Field(default="", max_length=200)
    exclude: list[str] = Field(default_factory=list, max_length=200)


class GeneratedItem(BaseModel):
    type: GenType
    front: str = ""
    back: str = ""
    title: str = ""
    body: str = ""
    sources: list[SlideRef] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    ref: str = ""
    key: str = ""  # echo back in `exclude` so Next never repeats
    suggested: NoteDestination | None = None


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def item_key(it: GeneratedItem) -> str:
    return norm(it.front or it.title + " " + it.body[:200])


class _Block(BaseModel):
    index: int
    source_id: str
    label: str
    pyq: bool
    pages: list[tuple[int, str]]


def _blocks(st: Storage, course_id: str, req: GenRequest) -> list[_Block]:
    ids: list[str] = []
    for lid in req.lecture_ids:
        ids.extend(s for s in get_lecture(st, course_id, lid).source_ids if s not in ids)
    ids.extend(s for s in req.source_ids if s not in ids)
    if not ids:
        raise LLMError("Pick at least one source or lecture to generate from.")
    blocks = []
    for i, sid in enumerate(ids, 1):
        meta = get_source(st, course_id, sid)
        doc = extract_source(st, course_id, meta)
        blocks.append(_Block(index=i, source_id=sid, label=meta.filename, pyq=meta.kind == "pyq",
                             pages=[(s.number, s.text) for s in doc.slides if s.text.strip()]))
    return blocks


def _format_sources(blocks: list[_Block], rotate: int) -> str:
    """Fit into MAX_CHARS; rotate the window on each Next so items vary across the deck."""
    budget = MAX_CHARS // max(len(blocks), 1)
    parts = []
    for b in blocks:
        pages = b.pages
        if pages:
            k = (rotate * 5) % len(pages)
            pages = pages[k:] + pages[:k]
        used, chunks = 0, []
        for num, text in pages:
            snippet = text.strip()[:1200]
            if used + len(snippet) > budget and chunks:
                break
            used += len(snippet)
            chunks.append(f"[Source {b.index} · page {num}]\n{snippet}")
        head = f"=== Source {b.index}: {b.label}{' (PAST PAPER)' if b.pyq else ''} ==="
        parts.append(head + "\n" + "\n\n".join(chunks))
    return "\n\n".join(parts)


def generate_one(
    st: Storage, provider: LLMProvider, prompts: PromptLibrary, model: str, course_id: str, req: GenRequest,
) -> GeneratedItem:
    if req.type == "explain" and not req.topic.strip():
        raise LLMError("Type the topic you want explained.")
    blocks = _blocks(st, course_id, req)
    p = prompts.get("generate_items")
    steer = " ".join([CHIP_TEXT[c] for c in req.chips] + ([f"Student's request: {req.steer.strip()}"] if req.steer.strip() else []))
    exclude_text = "\n".join(f"- {e[:200]}" for e in req.exclude[-30:]) or "(none)"
    seen = {norm(e) for e in req.exclude}
    for attempt in range(2):
        system = p.section(
            "system",
            kind=p.section(f"kind: {req.type}", topic=req.topic.strip()),
            exclude=exclude_text,
            steer=steer,
        )
        user = p.section("user", sources=_format_sources(blocks, len(req.exclude) + attempt))
        out = provider.structured(
            [ChatMessage(role="system", content=system), ChatMessage(role="user", content=user)],
            model, GenOut, tag=f"generate_{req.type}",
        )
        item = GeneratedItem(type=req.type, front=out.front.strip(), back=out.back.strip(), title=out.title.strip(),
                             body=out.body.strip(), ref=out.ref.strip()[:80])
        by_index = {b.index: b for b in blocks}
        for c in out.cites:
            b = by_index.get(c.source)
            if b and any(n == c.page for n, _ in b.pages):
                ref = SlideRef(source_id=b.source_id, slide=c.page)
                if ref not in item.sources:
                    item.sources.append(ref)
        item.source_ids = [b.source_id for b in blocks]
        if not (item.front or item.body):
            continue
        item.key = item_key(item)
        if item.key in seen:
            continue  # AC: Next never repeats an earlier item in the session
        return item
    raise LLMError("Couldn't come up with a new item from these sources. Try other sources or a different steer.")


# --------------------------------------------------------------------------- where to save

class PickOut(BaseModel):
    option: int


def course_nodes(st: Storage, course_id: str, lecture_ids: list[str] | None = None) -> list[NoteDestination]:
    out: list[NoteDestination] = []
    for lec in list_lectures(st, course_id):
        if lecture_ids and lec.id not in lecture_ids:
            continue
        path = st.paths.map(course_id, lec.id)
        if not st.exists(path):
            continue
        doc = st.read_doc(path, MapDoc)

        def walk(nid: str, trail: list[str]) -> None:
            n = doc.nodes[nid]
            if nid != doc.root_id:
                out.append(NoteDestination(course_id=course_id, lecture_id=lec.id, node_id=nid,
                                           label=" › ".join([lec.title, *trail, n.label])))
            for c in n.children:
                if c in doc.nodes:
                    walk(c, trail + ([n.label] if nid != doc.root_id else []))

        walk(doc.root_id, [])
    return out


def suggest_node(
    st: Storage, provider: LLMProvider, prompts: PromptLibrary, model: str, course_id: str,
    item: GeneratedItem, lecture_ids: list[str],
) -> NoteDestination:
    options = course_nodes(st, course_id, lecture_ids or None) or course_nodes(st, course_id)
    fallback = NoteDestination(course_id=course_id, label="Course (unassigned)")
    if not options:
        return fallback
    options = options[:250]
    p = prompts.get("suggest_node")
    text = item.front or f"{item.title}\n{item.body[:600]}"
    listing = "\n".join(f"{i}. {d.label}" for i, d in enumerate(options, 1))
    try:
        out = provider.structured(
            [ChatMessage(role="system", content=p.section("system")),
             ChatMessage(role="user", content=p.section("user", item=text, options=listing))],
            model, PickOut, tag="suggest_node",
        )
    except LLMError:
        return fallback
    if 1 <= out.option <= len(options):
        return options[out.option - 1]
    return fallback
