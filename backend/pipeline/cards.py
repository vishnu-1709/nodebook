"""Flashcards from a node's slides or from a note (SPEC §5.12 card sources)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from backend.core.schemas import MapDoc, PracticeItem, PracticeOrigin
from backend.core.storage import Storage
from backend.llm.base import ChatMessage, LLMError, LLMProvider
from backend.llm.prompts import PromptLibrary
from backend.pipeline.context import format_slide_texts, node_path, refs_for_numbers, slide_texts


class CardOut(BaseModel):
    front: str
    back: str
    slide: int = 0


class CardsOut(BaseModel):
    cards: list[CardOut] = Field(default_factory=list)


def _norm(s: str) -> str:
    return " ".join(s.lower().split())


def cards_from_slides(st: Storage, provider: LLMProvider, prompts: PromptLibrary, model: str, course_id: str,
                      doc: MapDoc, node_id: str, existing: list[str], count: int = 3) -> list[PracticeItem]:
    node = doc.nodes[node_id]
    if not node.sources:
        raise LLMError("This topic has no slides linked, so there's nothing to make cards from.")
    p = prompts.get("node_cards")
    msg = p.section("slides", path=" › ".join(node_path(doc, node_id)), count=count,
                    existing="; ".join(existing[-20:]) or "none",
                    slides=format_slide_texts(slide_texts(st, course_id, node.sources)))
    out = provider.structured([ChatMessage(role="system", content=p.section("system")),
                               ChatMessage(role="user", content=msg)], model, CardsOut, tag="node_cards")
    seen = {_norm(e) for e in existing}
    items: list[PracticeItem] = []
    for c in out.cards:
        if not c.front.strip() or _norm(c.front) in seen:
            continue
        seen.add(_norm(c.front))
        refs = refs_for_numbers([c.slide], node.sources)
        items.append(PracticeItem(type="card", node_id=node_id, front=c.front.strip(), back=c.back.strip(),
                                  origin=PracticeOrigin(kind="node", source_ids=[r.source_id for r in refs],
                                                        ref=f"slide {refs[0].slide}" if refs else "")))
        if len(items) == count:
            break
    if not items:
        raise LLMError("The model didn't come up with new cards. Try again.")
    return items


def cards_from_note(provider: LLMProvider, prompts: PromptLibrary, model: str, doc: MapDoc | None,
                    node_id: str | None, note: str) -> list[PracticeItem]:
    p = prompts.get("node_cards")
    path = " › ".join(node_path(doc, node_id)) if doc and node_id else "general"
    out = provider.structured([ChatMessage(role="system", content=p.section("system")),
                               ChatMessage(role="user", content=p.section("note", path=path, note=note))],
                              model, CardsOut, tag="node_cards")
    items = [PracticeItem(type="card", node_id=node_id, front=c.front.strip(), back=c.back.strip(),
                          origin=PracticeOrigin(kind="note", ref="from a note"))
             for c in out.cards[:2] if c.front.strip()]
    if not items:
        raise LLMError("Couldn't make a card from this note.")
    return items
