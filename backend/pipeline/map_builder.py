"""Slides → validated mind map (SPEC §4).

extract (done by the caller) → chunk → per-chunk topics → merge → enforce
caps in code → validate (retry once) → fallback flat map → coverage.
"""

from __future__ import annotations

import base64
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from backend.core.ids import new_id
from backend.core.schemas import MapDoc, Node, Slide, SlideRef
from backend.llm.base import ChatMessage, LLMError, LLMProvider, StructuredOutputError
from backend.llm.prompts import PromptLibrary
from backend.pipeline.coverage import uncovered_slides

CHUNK_SIZE = 12
MAX_DEPTH = 3  # levels below root
MAX_CHILDREN = 7
MAX_LABEL_WORDS = 6
SLIDE_TEXT_LIMIT = 1200
VISION_TEXT_THRESHOLD = 80

Progress = Callable[[str, float, str], None]


# --------------------------------------------------------------------------- LLM output shapes

class TopicOut(BaseModel):
    label: str
    slides: list[int] = Field(default_factory=list)


class ChunkTopic(BaseModel):
    label: str
    slides: list[int] = Field(default_factory=list)
    subtopics: list[TopicOut] = Field(default_factory=list)


class ChunkResult(BaseModel):
    topics: list[ChunkTopic]


class Level3(BaseModel):
    label: str
    slides: list[int] = Field(default_factory=list)


class Level2(BaseModel):
    label: str
    slides: list[int] = Field(default_factory=list)
    children: list[Level3] = Field(default_factory=list)


class Level1(BaseModel):
    label: str
    slides: list[int] = Field(default_factory=list)
    children: list[Level2] = Field(default_factory=list)


class MergeResult(BaseModel):
    topics: list[Level1]


# --------------------------------------------------------------------------- inputs / outputs

@dataclass
class DeckSlide:
    ref: SlideRef
    slide: Slide


@dataclass
class BuildInput:
    lecture_id: str
    lecture_title: str
    slides: list[DeckSlide]  # global order; global number = index + 1
    model: str
    vision: bool = False
    image_for: Callable[[SlideRef], bytes | None] | None = None


@dataclass
class BuildResult:
    map: MapDoc
    uncovered: list[SlideRef]
    fallback: bool = False
    warnings: list[str] = field(default_factory=list)


class TreeError(ValueError):
    pass


# --------------------------------------------------------------------------- draft tree + rules

@dataclass
class Draft:
    label: str
    slides: set[int] = field(default_factory=set)
    children: list[Draft] = field(default_factory=list)


_WS = re.compile(r"\s+")


def clean_label(label: str) -> str:
    label = _WS.sub(" ", label or "").strip().strip("-–—•*:;,. ").strip()
    label = label.strip("\"'`")
    words = label.split(" ")
    if len(words) > MAX_LABEL_WORDS:
        label = " ".join(words[:MAX_LABEL_WORDS]).rstrip(",;:-–—")
    return label


def norm_key(label: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", label.lower()).strip()


def _all_slides(d: Draft) -> set[int]:
    out = set(d.slides)
    for c in d.children:
        out |= _all_slides(c)
    return out


def _distance(a: set[int], b: set[int]) -> int:
    if not a or not b:
        return 10**6
    return min(abs(x - y) for x in a for y in b)


def normalize(topics: list[Draft], total_slides: int, root_label: str = "") -> list[Draft]:
    """Enforce SPEC §4 constraints in code. Returns the root's children."""
    valid = set(range(1, total_slides + 1))

    def clean(d: Draft, depth: int) -> Draft | None:
        d.label = clean_label(d.label)
        d.slides = {s for s in d.slides if s in valid}
        kids = [k for k in (clean(c, depth + 1) for c in d.children) if k is not None]
        if depth >= MAX_DEPTH:
            # flatten anything deeper into this node
            for k in kids:
                d.slides |= _all_slides(k)
            kids = []
        d.children = kids
        if not d.slides:
            d.slides = set().union(*(_all_slides(k) for k in kids)) if kids else set()
        if not d.label or not d.slides:
            return None
        return d

    roots = [r for r in (clean(t, 1) for t in topics) if r is not None]

    # global de-duplication (pre-order: first occurrence wins)
    seen: dict[str, tuple[Draft, int]] = {}
    root_key = norm_key(clean_label(root_label))

    def dedupe(siblings: list[Draft], depth: int) -> list[Draft]:
        out: list[Draft] = []
        for d in siblings:
            key = norm_key(d.label)
            if key in seen:
                keep, kdepth = seen[key]
                keep.slides |= d.slides
                if kdepth < MAX_DEPTH:
                    keep.children.extend(d.children)
                else:
                    keep.slides |= _all_slides(d)
                continue
            seen[key] = (d, depth)
            out.append(d)
        for d in out:
            d.children = dedupe(d.children, depth + 1)
        return out

    # a top-level topic named like the lecture itself: lift its children up a level
    lifted: list[Draft] = []
    for r in roots:
        if root_key and norm_key(r.label) == root_key:
            if r.children:
                lifted.extend(r.children)
                continue
            r.label = clean_label(f"{r.label} overview")
        lifted.append(r)
    roots = dedupe(lifted, 1)

    def cap(siblings: list[Draft], depth: int) -> list[Draft]:
        siblings = sorted(siblings, key=lambda d: min(_all_slides(d) or {10**6}))
        while len(siblings) > MAX_CHILDREN:
            # fold the smallest node into its nearest sibling (by slide distance)
            victim = min(siblings, key=lambda d: (len(_all_slides(d)), -min(_all_slides(d))))
            others = [s for s in siblings if s is not victim]
            vs = _all_slides(victim)
            target = min(others, key=lambda o: _distance(_all_slides(o), vs))
            if depth < MAX_DEPTH:
                target.children.append(victim)
            else:
                target.slides |= vs
            siblings = others
        for d in siblings:
            d.children = cap(d.children, depth + 1)
        return siblings

    roots = cap(roots, 1)
    validate_drafts(roots, total_slides)
    return roots


def validate_drafts(roots: list[Draft], total_slides: int) -> None:
    if not roots:
        raise TreeError("the map has no topics")
    labels: set[str] = set()

    def walk(d: Draft, depth: int) -> None:
        if depth > MAX_DEPTH:
            raise TreeError(f"'{d.label}' is deeper than {MAX_DEPTH} levels")
        if len(d.children) > MAX_CHILDREN:
            raise TreeError(f"'{d.label}' has more than {MAX_CHILDREN} children")
        if not d.slides:
            raise TreeError(f"'{d.label}' has no source slide")
        if any(s < 1 or s > total_slides for s in d.slides):
            raise TreeError(f"'{d.label}' cites a slide that does not exist")
        if len(d.label.split()) > MAX_LABEL_WORDS:
            raise TreeError(f"label '{d.label}' is longer than {MAX_LABEL_WORDS} words")
        key = norm_key(d.label)
        if key in labels:
            raise TreeError(f"duplicate label '{d.label}'")
        labels.add(key)
        for c in d.children:
            walk(c, depth + 1)

    if len(roots) > MAX_CHILDREN:
        raise TreeError(f"the root has more than {MAX_CHILDREN} children")
    for r in roots:
        walk(r, 1)


# --------------------------------------------------------------------------- conversions

def drafts_from_chunk(res: ChunkResult) -> list[Draft]:
    return [
        Draft(t.label, set(t.slides), [Draft(s.label, set(s.slides)) for s in t.subtopics])
        for t in res.topics
    ]


def drafts_from_merge(res: MergeResult) -> list[Draft]:
    return [
        Draft(
            a.label,
            set(a.slides),
            [Draft(b.label, set(b.slides), [Draft(c.label, set(c.slides)) for c in b.children]) for b in a.children],
        )
        for a in res.topics
    ]


def to_map_doc(lecture_id: str, title: str, roots: list[Draft], slides: list[DeckSlide]) -> MapDoc:
    root = Node(id=new_id(), label=clean_label(title) or "Lecture", origin="ai",
                sources=[slides[0].ref] if slides else [])
    nodes: dict[str, Node] = {root.id: root}

    def add(d: Draft, parent: Node) -> None:
        n = Node(
            id=new_id(),
            label=d.label,
            parent_id=parent.id,
            sources=[slides[s - 1].ref for s in sorted(d.slides)],
            origin="ai",
        )
        nodes[n.id] = n
        parent.children.append(n.id)
        for c in d.children:
            add(c, n)

    for r in roots:
        add(r, root)
    return MapDoc(lecture_id=lecture_id, root_id=root.id, nodes=nodes)


# --------------------------------------------------------------------------- the pipeline

def _range_label(first: int, last: int) -> str:
    return f"Slide {first}" if first == last else f"Slides {first}–{last}"


def format_slides(slides: list[DeckSlide], start: int) -> str:
    out = []
    for i, ds in enumerate(slides):
        n = start + i
        text = ds.slide.text.strip()
        if len(text) > SLIDE_TEXT_LIMIT:
            text = text[:SLIDE_TEXT_LIMIT] + " …"
        if not text:
            text = "(no text on this slide)" + (" — it contains a figure" if ds.slide.has_images else "")
        out.append(f"[Slide {n}]\n{text}")
    return "\n\n".join(out)


def format_chunks(chunks: list[tuple[int, int, list[Draft]]]) -> str:
    lines: list[str] = []
    for i, (first, last, drafts) in enumerate(chunks, 1):
        lines.append(f"Part {i} (slides {first}–{last}):")
        for d in drafts:
            lines.append(f"- {d.label} (slides {', '.join(map(str, sorted(d.slides)))})")
            for c in d.children:
                lines.append(f"  - {c.label} (slides {', '.join(map(str, sorted(c.slides)))})")
    return "\n".join(lines)


class MapBuilder:
    def __init__(self, provider: LLMProvider, prompts: PromptLibrary) -> None:
        self.provider = provider
        self.prompts = prompts

    def build(self, inp: BuildInput, progress: Progress | None = None) -> BuildResult:
        report = progress or (lambda *_: None)
        total = len(inp.slides)
        if total == 0:
            raise TreeError("this deck has no slides")
        warnings: list[str] = []

        chunks = [(i, inp.slides[i : i + CHUNK_SIZE]) for i in range(0, total, CHUNK_SIZE)]
        chunk_drafts: list[tuple[int, int, list[Draft]]] = []
        for ci, (start, part) in enumerate(chunks):
            first, last = start + 1, start + len(part)
            report("topics", 0.1 + 0.6 * ci / len(chunks), f"Finding topics in slides {first}–{last}")
            drafts = self._chunk(inp, part, first, last, total)
            if drafts is None:
                warnings.append(f"Couldn't read topics from slides {first}–{last}; added them as one node.")
                drafts = [Draft(_range_label(first, last), set(range(first, last + 1)))]
            chunk_drafts.append((first, last, drafts))

        report("merge", 0.75, "Building the map")
        fallback = False
        roots: list[Draft] | None = None
        if len(chunk_drafts) == 1:
            try:
                roots = normalize(chunk_drafts[0][2], total, inp.lecture_title)
            except TreeError as exc:
                warnings.append(f"Map check failed: {exc}")
        else:
            roots = self._merge(inp, chunk_drafts, total, warnings)

        if roots is None:
            fallback = True
            flat = [Draft(d.label, _all_slides(d)) for _, _, ds in chunk_drafts for d in ds]
            try:
                roots = normalize(flat, total, inp.lecture_title)
            except TreeError:
                roots = normalize(
                    [Draft(_range_label(f, l), set(range(f, l + 1))) for f, l, _ in chunk_drafts], total
                )

        report("coverage", 0.95, "Checking which slides are covered")
        doc = to_map_doc(inp.lecture_id, inp.lecture_title, roots, inp.slides)
        uncovered = uncovered_slides(doc, [(ds.ref, ds.slide) for ds in inp.slides])
        return BuildResult(map=doc, uncovered=uncovered, fallback=fallback, warnings=warnings)

    # -- steps -----------------------------------------------------------------
    def _chunk(self, inp: BuildInput, part: list[DeckSlide], first: int, last: int, total: int) -> list[Draft] | None:
        p = self.prompts.get("map_chunk")
        images: list[str] = []
        image_note = ""
        if inp.vision and inp.image_for is not None:
            for i, ds in enumerate(part):
                if ds.slide.has_images and len(ds.slide.text) < VISION_TEXT_THRESHOLD:
                    png = inp.image_for(ds.ref)
                    if png:
                        images.append(base64.b64encode(png).decode("ascii"))
                        image_note += f"\nAn image of slide {first + i} is attached."
        user = p.section(
            "user", lecture_title=inp.lecture_title, first=first, last=last, total=total,
            slides=format_slides(part, first),
        ) + image_note
        messages = [ChatMessage(role="system", content=p.section("system")),
                    ChatMessage(role="user", content=user, images=images)]
        for attempt in range(2):
            try:
                res = self.provider.structured(messages, inp.model, ChunkResult, tag="map_chunk")
                drafts = drafts_from_chunk(res)
                # keep only slides within this chunk
                rng = set(range(first, last + 1))
                for d in drafts:
                    d.slides &= rng
                    for c in d.children:
                        c.slides &= rng
                if drafts and not any(_all_slides(d) for d in drafts):
                    raise StructuredOutputError("no topic cited a slide from this part")
                return drafts  # [] = nothing study-worthy here; coverage will show it
            except StructuredOutputError as exc:
                if attempt == 0:
                    messages = messages + [ChatMessage(
                        role="user",
                        content=f"Your previous answer was rejected: {exc}. Reply again with valid JSON that cites slide numbers {first}–{last}.",
                    )]
                    continue
                return None
        return None

    def _merge(
        self, inp: BuildInput, chunk_drafts: list[tuple[int, int, list[Draft]]], total: int, warnings: list[str]
    ) -> list[Draft] | None:
        p = self.prompts.get("map_merge")
        messages = [
            ChatMessage(role="system", content=p.section("system")),
            ChatMessage(role="user", content=p.section(
                "user", lecture_title=inp.lecture_title, total=total, chunks=format_chunks(chunk_drafts))),
        ]
        for attempt in range(2):
            try:
                res = self.provider.structured(messages, inp.model, MergeResult, tag="map_merge")
                return normalize(drafts_from_merge(res), total, inp.lecture_title)
            except (StructuredOutputError, TreeError) as exc:
                if attempt == 0:
                    messages = messages + [ChatMessage(role="user", content=p.section("retry", error=str(exc)))]
                    continue
                warnings.append(f"Map check failed twice ({exc}); used a simpler flat map.")
                return None
            except LLMError:
                raise
        return None
