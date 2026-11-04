from __future__ import annotations

import json
from collections.abc import Iterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from backend.api.deps import get_ctx
from backend.core import maps as map_svc
from backend.core import threads as svc
from backend.core.context import AppContext
from backend.core.courses import NotFound
from backend.core.schemas import (
    Exchange,
    MapDoc,
    Message,
    Note,
    NotesDoc,
    PracticeDoc,
    PracticeItem,
    PracticeOrigin,
    RecentExchange,
)
from backend.core.usage import log_usage
from backend.llm.base import LLMError
from backend.pipeline.answer import USER_TEXT, Action, Mode, build_messages, plan_turn
from backend.pipeline.map_builder import clean_label

router = APIRouter(prefix="/courses/{course_id}/lectures/{lecture_id}", tags=["threads"])


class AskIn(BaseModel):
    content: str = Field(default="", max_length=8000)
    mode: Mode = "try_first"
    action: Action = "ask"
    exchange_id: str | None = None


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj, ensure_ascii=False)}\n\n"


@router.get("/nodes/{node_id}/thread")
def get_thread(course_id: str, lecture_id: str, node_id: str, ctx: AppContext = Depends(get_ctx)) -> svc.NodeThread:
    return svc.node_thread(ctx.storage, course_id, lecture_id, node_id)


@router.get("/threads/counts")
def counts(course_id: str, lecture_id: str, ctx: AppContext = Depends(get_ctx)) -> dict[str, int]:
    return svc.kept_counts(ctx.storage, course_id, lecture_id)


@router.post("/nodes/{node_id}/ask")
def ask(course_id: str, lecture_id: str, node_id: str, body: AskIn, ctx: AppContext = Depends(get_ctx)) -> StreamingResponse:
    st = ctx.storage
    doc = map_svc.load_map(st, course_id, lecture_id)
    if node_id not in doc.nodes:
        raise HTTPException(404, "node not found")
    content = USER_TEXT.get(body.action, body.content).strip()
    if not content:
        raise HTTPException(400, "Type a question first.")
    model = ctx.require_model("study")
    if body.exchange_id:
        owner, exchange, _ = svc.find_exchange(st, course_id, lecture_id, body.exchange_id)
        if owner != node_id:
            raise HTTPException(400, "That exchange belongs to another node.")
    else:
        exchange = svc.start_exchange(st, course_id, lecture_id, node_id, keep=ctx.settings.keep_all_questions)
    user_kind, section, ai_kind = plan_turn(body.action, body.mode)
    user_msg = Message(role="user", kind=user_kind, content=content)
    kept = svc.last_kept(st, course_id, lecture_id, node_id)
    messages = build_messages(st, ctx.prompts, course_id, doc, node_id, kept, exchange, user_msg, section)
    provider = ctx.provider
    log_usage(ctx, f"thread.{body.action}.{body.mode}")

    def stream() -> Iterator[str]:
        yield _sse({"type": "start", "exchange_id": exchange.id, "kept": exchange.kept_at is not None,
                    "user": user_msg.model_dump(), "kind": ai_kind})
        parts: list[str] = []
        try:
            for chunk in provider.chat_stream(messages, model, tag="node_answer"):
                parts.append(chunk)
                yield _sse({"type": "delta", "text": chunk})
        except LLMError as exc:
            yield _sse({"type": "error", "message": str(exc)})
            return
        answer = "".join(parts).strip() or "(The model returned an empty answer. Try again.)"
        saved = svc.append_messages(st, course_id, lecture_id, exchange.id, [
            user_msg, Message(role="assistant", kind=ai_kind, content=answer)])
        yield _sse({"type": "done", "exchange": saved.model_dump(mode="json")})

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/exchanges/{exchange_id}/keep")
def keep(course_id: str, lecture_id: str, exchange_id: str, ctx: AppContext = Depends(get_ctx)) -> Exchange:
    log_usage(ctx, "thread.keep")
    return svc.keep(ctx.storage, course_id, lecture_id, exchange_id)


@router.post("/exchanges/{exchange_id}/unkeep")
def unkeep(course_id: str, lecture_id: str, exchange_id: str, ctx: AppContext = Depends(get_ctx)) -> RecentExchange:
    return svc.unkeep(ctx.storage, course_id, lecture_id, exchange_id)


@router.delete("/exchanges/{exchange_id}", status_code=204)
def delete(course_id: str, lecture_id: str, exchange_id: str, ctx: AppContext = Depends(get_ctx)) -> None:
    svc.delete_exchange(ctx.storage, course_id, lecture_id, exchange_id)


def _qa(ex: Exchange) -> tuple[str, str]:
    q = next((m.content for m in ex.messages if m.role == "user" and m.kind == "question"), "")
    a = next((m.content for m in reversed(ex.messages) if m.role == "assistant" and m.kind == "answer"), "")
    if not a:
        a = next((m.content for m in reversed(ex.messages) if m.role == "assistant"), "")
    return q, a


@router.post("/exchanges/{exchange_id}/to-card", status_code=201)
def to_card(course_id: str, lecture_id: str, exchange_id: str, ctx: AppContext = Depends(get_ctx)) -> PracticeItem:
    st = ctx.storage
    node_id, ex, _ = svc.find_exchange(st, course_id, lecture_id, exchange_id)
    q, a = _qa(ex)
    if not q:
        raise HTTPException(400, "This exchange has no question to turn into a card.")
    item = PracticeItem(type="card", node_id=node_id, front=q, back=a,
                        origin=PracticeOrigin(kind="thread", ref=f"exchange {ex.id}"))
    with st.update_doc(st.paths.practice(course_id, lecture_id), PracticeDoc, PracticeDoc) as doc:
        doc.items.append(item)
    log_usage(ctx, "thread.to_card")
    return item


@router.post("/exchanges/{exchange_id}/to-note", status_code=201)
def to_note(course_id: str, lecture_id: str, exchange_id: str, ctx: AppContext = Depends(get_ctx)) -> Note:
    st = ctx.storage
    node_id, ex, _ = svc.find_exchange(st, course_id, lecture_id, exchange_id)
    q, a = _qa(ex)
    note = Note(text=f"{q}\n\n{a}".strip(), node_id=node_id, pinned_from=ex.id)
    with st.update_doc(st.paths.lecture_notes(course_id, lecture_id), NotesDoc, NotesDoc) as doc:
        doc.items.append(note)
    log_usage(ctx, "thread.to_note")
    return note


@router.post("/exchanges/{exchange_id}/to-node", status_code=201)
def to_node(course_id: str, lecture_id: str, exchange_id: str, ctx: AppContext = Depends(get_ctx)) -> MapDoc:
    st = ctx.storage
    node_id, ex, _ = svc.find_exchange(st, course_id, lecture_id, exchange_id)
    q, _ = _qa(ex)
    doc = map_svc.load_map(st, course_id, lecture_id)
    parent = doc.nodes.get(node_id)
    if parent is None:
        raise NotFound("node not found")
    label = clean_label(q.rstrip("?")) or "New topic"
    doc, _ = map_svc.add_nodes(st, course_id, lecture_id, node_id, [(label, list(parent.sources))])
    log_usage(ctx, "thread.to_node")
    return doc
