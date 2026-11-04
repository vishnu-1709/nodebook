"""Build the prompt for a node Q&A turn (SPEC §5.5)."""

from __future__ import annotations

from typing import Literal

from backend.core.schemas import Exchange, MapDoc, Message, MessageKind
from backend.core.storage import Storage
from backend.llm.base import ChatMessage
from backend.llm.prompts import PromptLibrary
from backend.pipeline.context import format_slide_texts, node_path, slide_texts

Mode = Literal["normal", "try_first", "hint"]
Action = Literal["ask", "attempt", "why", "example"]

USER_TEXT = {"why": "Explain why.", "example": "Give an example."}


def _history(kept: list[Exchange], exclude: str | None) -> str:
    rows = []
    for ex in kept:
        if ex.id == exclude:
            continue
        q = next((m.content for m in ex.messages if m.role == "user"), "")
        a = next((m.content for m in reversed(ex.messages) if m.role == "assistant"), "")
        if q:
            rows.append(f"Q: {q.strip()[:400]}\nA: {a.strip()[:600]}")
    return "\n\n".join(rows) or "(none)"


def plan_turn(action: Action, mode: Mode) -> tuple[MessageKind, str, MessageKind]:
    """(user message kind, prompt mode section, assistant message kind)."""
    if action == "attempt":
        return ("attempt", "attempt_hint" if mode == "hint" else "attempt", "hint" if mode == "hint" else "answer")
    if action in ("why", "example"):
        return ("question", action, "answer")
    if mode == "try_first":
        return ("question", "try_first", "try_first")
    if mode == "hint":
        return ("question", "hint", "hint")
    return ("question", "normal", "answer")


def build_messages(
    st: Storage, prompts: PromptLibrary, course_id: str, doc: MapDoc, node_id: str,
    kept: list[Exchange], exchange: Exchange, user_msg: Message, mode_section: str,
) -> list[ChatMessage]:
    node = doc.nodes[node_id]
    p = prompts.get("node_answer")
    slides = format_slide_texts(slide_texts(st, course_id, node.sources))
    system = p.section(
        "system",
        path=" › ".join(node_path(doc, node_id)),
        slides=slides,
        history=_history(kept, exchange.id),
        mode=p.section(f"mode: {mode_section}"),
    )
    msgs = [ChatMessage(role="system", content=system)]
    for m in exchange.messages:
        msgs.append(ChatMessage(role=m.role, content=m.content))
    msgs.append(ChatMessage(role="user", content=user_msg.content))
    return msgs
