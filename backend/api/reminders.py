from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.api.deps import get_ctx
from backend.core import reminders as svc
from fastapi.responses import Response

from backend.core.context import AppContext
from backend.core.ics import reminders_ics
from backend.core.schemas import Reminder, ReminderLink, TagColour
from backend.core.today import TodayOut, build_today
from backend.core.usage import log_usage

router = APIRouter(tags=["reminders"])


class ParseIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)


class ReminderIn(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    due_at: str
    tags: list[str] = Field(default_factory=list)
    link: ReminderLink | None = None
    course_id: str | None = None


class ReminderPatch(BaseModel):
    text: str | None = Field(default=None, max_length=500)
    due_at: str | None = None
    tags: list[str] | None = None
    done: bool | None = None


class TagIn(BaseModel):
    name: str = Field(min_length=1, max_length=30)
    colour: str = Field(pattern=r"^tag-[1-6]$")


class RemindersOut(BaseModel):
    items: list[Reminder]
    custom_tags: list[TagColour]
    builtin_tags: list[str]


class SessionIn(BaseModel):
    started_at: str
    ended_at: str
    work_min: int = Field(ge=1, le=600)
    completed: bool = True


@router.post("/reminders/parse")
def parse(body: ParseIn) -> svc.ParsedReminder:
    return svc.parse_reminder(body.text)


@router.get("/reminders")
def list_all(ctx: AppContext = Depends(get_ctx)) -> RemindersOut:
    doc = svc.list_reminders(ctx.storage)
    return RemindersOut(items=sorted(doc.items, key=svc.due), custom_tags=doc.custom_tags, builtin_tags=svc.BUILTIN_TAGS)


@router.post("/reminders", status_code=201)
def create(body: ReminderIn, ctx: AppContext = Depends(get_ctx)) -> Reminder:
    try:
        datetime.fromisoformat(body.due_at)
    except ValueError as exc:
        raise HTTPException(400, "That date isn't valid.") from exc
    log_usage(ctx, "reminder.create")
    return svc.add_reminder(ctx.storage, body.text, body.due_at, body.tags, body.link, body.course_id)


@router.patch("/reminders/{reminder_id}")
def patch(reminder_id: str, body: ReminderPatch, ctx: AppContext = Depends(get_ctx)) -> Reminder:
    if body.due_at is not None:
        try:
            datetime.fromisoformat(body.due_at)
        except ValueError as exc:
            raise HTTPException(400, "That date isn't valid.") from exc
    return svc.update_reminder(ctx.storage, reminder_id, **body.model_dump(exclude_none=True))


@router.delete("/reminders/{reminder_id}", status_code=204)
def delete(reminder_id: str, ctx: AppContext = Depends(get_ctx)) -> None:
    svc.delete_reminder(ctx.storage, reminder_id)


@router.put("/reminders/tags")
def set_tag(body: TagIn, ctx: AppContext = Depends(get_ctx)) -> list[TagColour]:
    return svc.set_tag_colour(ctx.storage, body.name.lower(), body.colour)


@router.get("/reminders.ics")
def all_ics(ctx: AppContext = Depends(get_ctx)) -> Response:
    """Every open reminder as one calendar file."""
    items = [r for r in svc.list_reminders(ctx.storage).items if not r.done]
    return Response(reminders_ics(items), media_type="text/calendar",
                    headers={"Content-Disposition": 'attachment; filename="nodebook-reminders.ics"'})


@router.get("/reminders/{reminder_id}.ics")
def one_ics(reminder_id: str, ctx: AppContext = Depends(get_ctx)) -> Response:
    r = next((x for x in svc.list_reminders(ctx.storage).items if x.id == reminder_id), None)
    if r is None:
        raise HTTPException(404, "reminder not found")
    log_usage(ctx, "reminder.ics")
    return Response(reminders_ics([r]), media_type="text/calendar",
                    headers={"Content-Disposition": 'attachment; filename="reminder.ics"'})


@router.get("/today")
def today(ctx: AppContext = Depends(get_ctx)) -> TodayOut:
    return build_today(ctx.storage)


@router.post("/sessions", status_code=201)
def log_session(body: SessionIn, ctx: AppContext = Depends(get_ctx)) -> SessionIn:
    """Pomodoro sessions, append-only (SPEC §3 sessions.jsonl)."""
    ctx.storage.append_jsonl(ctx.storage.paths.sessions, body)
    log_usage(ctx, "pomodoro.session")
    return body


