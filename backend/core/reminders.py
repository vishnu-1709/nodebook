"""Reminders (SPEC §5.10): natural-language dates + #tags. #exam drives the
exam countdown on Today."""

from __future__ import annotations

import re
from datetime import datetime, timedelta

from pydantic import BaseModel

from backend.core.courses import NotFound
from backend.core.schemas import Reminder, ReminderLink, RemindersDoc, TagColour
from backend.core.storage import Storage

BUILTIN_TAGS = ["exam", "assignment", "lab", "quiz", "revise"]
_TAG_RE = re.compile(r"(?<!\w)#([\w-]{1,30})")
_TIME_RE = re.compile(r"\b(\d{1,2}(:\d{2})?\s*(am|pm)|\d{1,2}:\d{2}|noon|midnight|morning|evening|tonight)\b", re.I)
DEFAULT_HOUR = 9


class ParsedReminder(BaseModel):
    text: str
    due_at: str | None
    tags: list[str]
    matched: str = ""


def local_now() -> datetime:
    return datetime.now().astimezone()


def parse_reminder(raw: str, now: datetime | None = None) -> ParsedReminder:
    from dateparser.search import search_dates

    now = now or local_now()
    tags = []
    for t in _TAG_RE.findall(raw):
        t = t.lower()
        if t not in tags:
            tags.append(t)
    text = " ".join(_TAG_RE.sub("", raw).split())
    found = search_dates(
        text,
        languages=["en"],
        settings={
            "PREFER_DATES_FROM": "future",
            "RELATIVE_BASE": now.replace(tzinfo=None),
            "RETURN_AS_TIMEZONE_AWARE": False,
        },
    ) or []
    # skip bare numbers like "ch 3" that dateparser sometimes reads as dates
    found = [(s, d) for s, d in found if not re.fullmatch(r"\d{1,2}", s.strip())]
    if not found:
        return ParsedReminder(text=text or raw.strip(), due_at=None, tags=tags)
    matched, dt = found[0]
    if not _TIME_RE.search(matched) and dt.hour == 0 and dt.minute == 0:
        dt = dt.replace(hour=DEFAULT_HOUR, minute=0)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=now.tzinfo)
    if dt < now - timedelta(days=1) and not re.search(r"\b(19|20)\d\d\b", matched):
        dt = dt.replace(year=dt.year + 1)  # "14 nov" after Nov 14 → next year
    return ParsedReminder(text=text, due_at=dt.isoformat(timespec="minutes"), tags=tags, matched=matched)


def list_reminders(st: Storage) -> RemindersDoc:
    return st.read_doc(st.paths.reminders, RemindersDoc, RemindersDoc)


def add_reminder(st: Storage, text: str, due_at: str, tags: list[str], link: ReminderLink | None,
                 course_id: str | None) -> Reminder:
    datetime.fromisoformat(due_at)  # validate
    r = Reminder(text=text.strip(), due_at=due_at, tags=[t.lower() for t in tags], link=link,
                 course_id=course_id or (link.course_id if link else None))
    with st.update_doc(st.paths.reminders, RemindersDoc, RemindersDoc) as doc:
        doc.items.append(r)
        known = set(BUILTIN_TAGS) | {t.name for t in doc.custom_tags}
        for t in r.tags:
            if t not in known:
                doc.custom_tags.append(TagColour(name=t, colour=f"tag-{(len(doc.custom_tags) % 6) + 1}"))
                known.add(t)
    return r


def update_reminder(st: Storage, reminder_id: str, **fields: object) -> Reminder:
    with st.update_doc(st.paths.reminders, RemindersDoc, RemindersDoc) as doc:
        for r in doc.items:
            if r.id == reminder_id:
                for k, v in fields.items():
                    if v is not None:
                        setattr(r, k, v)
                return r
    raise NotFound("reminder not found")


def delete_reminder(st: Storage, reminder_id: str) -> None:
    with st.update_doc(st.paths.reminders, RemindersDoc, RemindersDoc) as doc:
        doc.items = [r for r in doc.items if r.id != reminder_id]


def set_tag_colour(st: Storage, name: str, colour: str) -> list[TagColour]:
    with st.update_doc(st.paths.reminders, RemindersDoc, RemindersDoc) as doc:
        for t in doc.custom_tags:
            if t.name == name:
                t.colour = colour
                break
        else:
            doc.custom_tags.append(TagColour(name=name, colour=colour))
        return doc.custom_tags


def due(r: Reminder) -> datetime:
    d = datetime.fromisoformat(r.due_at)
    return d if d.tzinfo else d.replace(tzinfo=local_now().tzinfo)
