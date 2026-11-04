from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from backend.api.deps import get_ctx
from backend.core import maps as map_svc
from backend.core import review as svc
from backend.core.anki import export_apkg
from backend.core.context import AppContext
from backend.core.courses import NotFound, get_course, get_lecture
from backend.core.notes import list_notes
from backend.core.schemas import MapDoc, PracticeDoc, PracticeItem, PracticeOrigin
from backend.core.usage import log_usage
from backend.pipeline.cards import cards_from_note, cards_from_slides

router = APIRouter(tags=["review"])


class QueueOut(BaseModel):
    items: list[svc.ReviewItem]
    total: int


class RateIn(BaseModel):
    course_id: str
    lecture_id: str | None = None
    item_id: str
    rating: svc.RatingNum
    duration_ms: int | None = Field(default=None, ge=0)


class RateOut(BaseModel):
    item: PracticeItem
    remaining: int


class CountsOut(BaseModel):
    total: int
    by_course: dict[str, int]


class NewItem(BaseModel):
    type: str = Field(pattern="^(card|question)$")
    node_id: str | None = None
    front: str = Field(min_length=1, max_length=4000)
    back: str = Field(default="", max_length=8000)


@router.get("/review/queue")
def get_queue(course_id: str | None = None, lecture_id: str | None = None, ctx: AppContext = Depends(get_ctx)) -> QueueOut:
    items = svc.queue(ctx.storage, course_id, lecture_id)
    return QueueOut(items=items, total=len(items))


@router.get("/review/counts")
def counts(ctx: AppContext = Depends(get_ctx)) -> CountsOut:
    by = svc.due_counts(ctx.storage)
    return CountsOut(total=sum(by.values()), by_course=by)


@router.post("/review/rate")
def rate(body: RateIn, ctx: AppContext = Depends(get_ctx)) -> RateOut:
    item = svc.rate(ctx.storage, body.course_id, body.lecture_id, body.item_id, body.rating, body.duration_ms)
    log_usage(ctx, f"review.rate.{body.rating}")
    return RateOut(item=item, remaining=len(svc.queue(ctx.storage, body.course_id)))


# --------------------------------------------------------------------------- practice CRUD (Practice tab)

def _ppath(ctx: AppContext, course_id: str, lecture_id: str):  # noqa: ANN202
    get_lecture(ctx.storage, course_id, lecture_id)
    return ctx.storage.paths.practice(course_id, lecture_id)


@router.post("/courses/{course_id}/lectures/{lecture_id}/practice", status_code=201)
def add_item(course_id: str, lecture_id: str, body: NewItem, ctx: AppContext = Depends(get_ctx)) -> PracticeItem:
    item = PracticeItem(type=body.type, node_id=body.node_id, front=body.front.strip(), back=body.back.strip(),  # type: ignore[arg-type]
                        answer_status="verified", origin=PracticeOrigin(kind="node", ref="written by you"))
    with ctx.storage.update_doc(_ppath(ctx, course_id, lecture_id), PracticeDoc, PracticeDoc) as doc:
        doc.items.append(item)
    log_usage(ctx, "practice.add")
    return item


@router.delete("/courses/{course_id}/lectures/{lecture_id}/practice/{item_id}", status_code=204)
def delete_item(course_id: str, lecture_id: str, item_id: str, ctx: AppContext = Depends(get_ctx)) -> None:
    with ctx.storage.update_doc(_ppath(ctx, course_id, lecture_id), PracticeDoc, PracticeDoc) as doc:
        before = len(doc.items)
        doc.items = [i for i in doc.items if i.id != item_id]
        if len(doc.items) == before:
            raise NotFound("practice item not found")


@router.post("/courses/{course_id}/lectures/{lecture_id}/nodes/{node_id}/practice/cards", status_code=201)
def cards_from_node(course_id: str, lecture_id: str, node_id: str, ctx: AppContext = Depends(get_ctx)) -> list[PracticeItem]:
    st = ctx.storage
    doc = map_svc.load_map(st, course_id, lecture_id)
    if node_id not in doc.nodes:
        raise HTTPException(404, "node not found")
    path = _ppath(ctx, course_id, lecture_id)
    existing = [i.front for i in st.read_doc(path, PracticeDoc, PracticeDoc).items if i.node_id == node_id]
    items = cards_from_slides(st, ctx.provider, ctx.prompts, ctx.require_model("study"), course_id, doc, node_id, existing)
    with st.update_doc(path, PracticeDoc, PracticeDoc) as pd:
        pd.items.extend(items)
    log_usage(ctx, "practice.cards_from_slides")
    return items


@router.post("/courses/{course_id}/lectures/{lecture_id}/notes/{note_id}/to-card", status_code=201)
def note_to_card(course_id: str, lecture_id: str, note_id: str, ctx: AppContext = Depends(get_ctx)) -> list[PracticeItem]:
    st = ctx.storage
    note = next((n for n in list_notes(st, course_id, lecture_id) if n.id == note_id), None)
    if note is None:
        raise NotFound("note not found")
    mp = st.paths.map(course_id, lecture_id)
    doc = st.read_doc(mp, MapDoc) if st.exists(mp) else None
    items = cards_from_note(ctx.provider, ctx.prompts, ctx.require_model("study"), doc, note.node_id, note.text)
    with st.update_doc(_ppath(ctx, course_id, lecture_id), PracticeDoc, PracticeDoc) as pd:
        pd.items.extend(items)
    log_usage(ctx, "practice.cards_from_note")
    return items


@router.get("/courses/{course_id}/anki")
def anki(course_id: str, lecture_id: str | None = None, ctx: AppContext = Depends(get_ctx)) -> Response:
    st = ctx.storage
    course = get_course(st, course_id)
    name = course.name
    if lecture_id:
        name = f"{course.name}::{get_lecture(st, course_id, lecture_id).title}"
    data = export_apkg(st, course_id, name, lecture_id)
    safe = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in name.replace("::", " - ")).strip() or "nodebook"
    log_usage(ctx, "anki.export")
    return Response(data, media_type="application/octet-stream",
                    headers={"Content-Disposition": f'attachment; filename="{safe}.apkg"'})
