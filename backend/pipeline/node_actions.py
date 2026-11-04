"""AI node actions (SPEC §5.3): expand, split, merge with sibling, simplify label.
Each returns a Proposal that the UI previews before applying."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from backend.core.maps import MapEditError
from backend.core.schemas import MapDoc, SlideRef
from backend.core.storage import Storage
from backend.llm.base import ChatMessage, LLMProvider
from backend.llm.prompts import PromptLibrary
from backend.pipeline.context import format_slide_texts, node_path, refs_for_numbers, slide_texts
from backend.pipeline.map_builder import clean_label

Action = Literal["expand", "split", "merge", "simplify"]


class PartOut(BaseModel):
    label: str
    slides: list[int] = Field(default_factory=list)


class ExpandOut(BaseModel):
    subtopics: list[PartOut]


class SplitOut(BaseModel):
    parts: list[PartOut]


class LabelOut(BaseModel):
    label: str


class ProposalPart(BaseModel):
    label: str
    sources: list[SlideRef] = Field(default_factory=list)


class Proposal(BaseModel):
    action: Action
    node_id: str
    sibling_id: str | None = None
    label: str | None = None
    parts: list[ProposalPart] = Field(default_factory=list)


def _parts(raw: list[PartOut], allowed: list[SlideRef], fallback: list[SlideRef]) -> list[ProposalPart]:
    out: list[ProposalPart] = []
    seen: set[str] = set()
    for p in raw:
        label = clean_label(p.label)
        if not label or label.lower() in seen:
            continue
        seen.add(label.lower())
        out.append(ProposalPart(label=label, sources=refs_for_numbers(p.slides, allowed) or list(fallback)))
    return out


def suggest(
    st: Storage, provider: LLMProvider, prompts: PromptLibrary, model: str,
    course_id: str, doc: MapDoc, node_id: str, action: Action, sibling_id: str | None = None,
) -> Proposal:
    node = doc.nodes.get(node_id)
    if node is None:
        raise MapEditError("node not found")
    p = prompts.get("node_actions")
    path = " › ".join(node_path(doc, node_id))
    system = ChatMessage(role="system", content=p.section("system"))

    if action == "expand":
        refs = node.sources
        slides = format_slide_texts(slide_texts(st, course_id, refs))
        existing = ", ".join(doc.nodes[c].label for c in node.children if c in doc.nodes) or "none"
        msg = p.section("expand", path=path, existing=existing, slides=slides)
        out = provider.structured([system, ChatMessage(role="user", content=msg)], model, ExpandOut, tag="node_expand")
        existing_keys = {doc.nodes[c].label.lower() for c in node.children if c in doc.nodes} | {node.label.lower()}
        parts = [x for x in _parts(out.subtopics[:5], refs, refs) if x.label.lower() not in existing_keys]
        if not parts:
            raise MapEditError("The model didn't find new subtopics in this node's slides.")
        return Proposal(action=action, node_id=node_id, parts=parts)

    if action == "split":
        if node.parent_id is None:
            raise MapEditError("The root can't be split.")
        refs = node.sources
        slides = format_slide_texts(slide_texts(st, course_id, refs))
        msg = p.section("split", path=path, slides=slides)
        out = provider.structured([system, ChatMessage(role="user", content=msg)], model, SplitOut, tag="node_split")
        parts = _parts(out.parts[:3], refs, refs)
        if len(parts) < 2:
            raise MapEditError("The model couldn't find two separate ideas in this node.")
        return Proposal(action=action, node_id=node_id, parts=parts)

    if action == "merge":
        if not sibling_id or sibling_id not in doc.nodes:
            raise MapEditError("Pick a sibling to merge with.")
        sib = doc.nodes[sibling_id]
        if sib.parent_id != node.parent_id or node.parent_id is None:
            raise MapEditError("Only siblings can be merged.")
        refs = node.sources + [s for s in sib.sources if s not in node.sources]
        slides = format_slide_texts(slide_texts(st, course_id, refs))
        parent = doc.nodes[node.parent_id].label
        msg = p.section("merge", a=node.label, b=sib.label, parent=parent, slides=slides)
        out = provider.structured([system, ChatMessage(role="user", content=msg)], model, LabelOut, tag="node_merge")
        return Proposal(action=action, node_id=node_id, sibling_id=sibling_id,
                        label=clean_label(out.label) or node.label)

    # simplify
    slides = format_slide_texts(slide_texts(st, course_id, node.sources))
    msg = p.section("simplify", path=path, label=node.label, slides=slides)
    out = provider.structured([system, ChatMessage(role="user", content=msg)], model, LabelOut, tag="node_simplify")
    return Proposal(action="simplify", node_id=node_id, label=clean_label(out.label) or node.label)
