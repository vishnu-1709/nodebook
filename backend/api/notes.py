from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.api.deps import get_ctx
from backend.core import notes as svc
from backend.core.context import AppContext
from backend.core.schemas import InboxItem, Note, NoteDestination
from backend.core.usage import log_usage
from backend.pipeline.file_note import destinations, suggest_destination

router = APIRouter(tags=["notes"])


class NoteIn(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    node_id: str | None = None


class NoteText(BaseModel):
    text: str = Field(min_length=1, max_length=20000)


class CaptureIn(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    course_id: str | None = None
    lecture_id: str | None = None
    node_id: str | None = None


@router.post("/notes/capture", status_code=201)
def capture(body: CaptureIn, ctx: AppContext = Depends(get_ctx)) -> svc.Captured:
    log_usage(ctx, "note.capture")
    return svc.capture(ctx.storage, body.text, body.course_id, body.lecture_id, body.node_id)


# course-level notes
@router.get("/courses/{course_id}/notes")
def course_notes(course_id: str, ctx: AppContext = Depends(get_ctx)) -> list[Note]:
    return svc.list_notes(ctx.storage, course_id)


@router.post("/courses/{course_id}/notes", status_code=201)
def add_course_note(course_id: str, body: NoteIn, ctx: AppContext = Depends(get_ctx)) -> Note:
    return svc.add_note(ctx.storage, course_id, None, body.text)


@router.patch("/courses/{course_id}/notes/{note_id}")
def edit_course_note(course_id: str, note_id: str, body: NoteText, ctx: AppContext = Depends(get_ctx)) -> Note:
    return svc.update_note(ctx.storage, course_id, None, note_id, body.text)


@router.delete("/courses/{course_id}/notes/{note_id}", status_code=204)
def delete_course_note(course_id: str, note_id: str, ctx: AppContext = Depends(get_ctx)) -> None:
    svc.delete_note(ctx.storage, course_id, None, note_id)


# lecture + node notes
@router.get("/courses/{course_id}/lectures/{lecture_id}/notes")
def lecture_notes(course_id: str, lecture_id: str, node_id: str | None = None,
                  ctx: AppContext = Depends(get_ctx)) -> list[Note]:
    return svc.list_notes(ctx.storage, course_id, lecture_id, node_id)


@router.post("/courses/{course_id}/lectures/{lecture_id}/notes", status_code=201)
def add_lecture_note(course_id: str, lecture_id: str, body: NoteIn, ctx: AppContext = Depends(get_ctx)) -> Note:
    return svc.add_note(ctx.storage, course_id, lecture_id, body.text, body.node_id)


@router.patch("/courses/{course_id}/lectures/{lecture_id}/notes/{note_id}")
def edit_lecture_note(course_id: str, lecture_id: str, note_id: str, body: NoteText,
                      ctx: AppContext = Depends(get_ctx)) -> Note:
    return svc.update_note(ctx.storage, course_id, lecture_id, note_id, body.text)


@router.delete("/courses/{course_id}/lectures/{lecture_id}/notes/{note_id}", status_code=204)
def delete_lecture_note(course_id: str, lecture_id: str, note_id: str, ctx: AppContext = Depends(get_ctx)) -> None:
    svc.delete_note(ctx.storage, course_id, lecture_id, note_id)


# inbox
@router.get("/inbox")
def inbox(ctx: AppContext = Depends(get_ctx)) -> list[InboxItem]:
    return svc.list_inbox(ctx.storage)


@router.get("/inbox/destinations")
def inbox_destinations(ctx: AppContext = Depends(get_ctx)) -> list[NoteDestination]:
    return destinations(ctx.storage)


@router.post("/inbox/{item_id}/suggest")
def inbox_suggest(item_id: str, ctx: AppContext = Depends(get_ctx)) -> InboxItem:
    item = next((i for i in svc.list_inbox(ctx.storage) if i.id == item_id), None)
    if item is None:
        from backend.core.courses import NotFound

        raise NotFound("inbox item not found")
    dest = suggest_destination(ctx.storage, ctx.provider, ctx.prompts, ctx.require_model("study"), item.text)
    return svc.set_suggestion(ctx.storage, item_id, dest or NoteDestination(label=""))


@router.post("/inbox/{item_id}/file")
def inbox_file(item_id: str, dest: NoteDestination, ctx: AppContext = Depends(get_ctx)) -> svc.Captured:
    log_usage(ctx, "inbox.file")
    return svc.file_item(ctx.storage, item_id, dest)


@router.delete("/inbox/{item_id}", status_code=204)
def inbox_delete(item_id: str, ctx: AppContext = Depends(get_ctx)) -> None:
    svc.delete_inbox_item(ctx.storage, item_id)
