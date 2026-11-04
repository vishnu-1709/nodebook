"""Pydantic models for everything stored on disk (SPEC §3).

Every top-level JSON document carries ``"schema": <int>`` (field ``schema_version``
in Python, because ``schema`` shadows a BaseModel attribute).
"""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.core.clock import now_iso
from backend.core.ids import new_id


class Model(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="ignore")


class Doc(Model):
    """A top-level JSON file. ``KIND`` names it for the migration registry."""

    KIND: ClassVar[str] = ""
    VERSION: ClassVar[int] = 1
    schema_version: int = Field(default=1, alias="schema")

    def model_post_init(self, __context: Any) -> None:
        # after migrations, a loaded doc is always at the current version
        self.schema_version = type(self).VERSION


# --------------------------------------------------------------------------- common

Status = Literal["not_started", "confused", "revising", "got_it"]
StatusMode = Literal["manual", "auto"]


class SlideRef(Model):
    source_id: str
    slide: int


# --------------------------------------------------------------------------- course

class Course(Doc):
    KIND: ClassVar[str] = "course"
    id: str = Field(default_factory=new_id)
    name: str
    lecture_order: list[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)


SourceKind = Literal["slides", "pyq", "notes", "textbook", "other"]


class SourceMeta(Model):
    id: str = Field(default_factory=new_id)
    filename: str
    ext: str
    kind: SourceKind = "slides"
    size: int = 0
    lecture_id: str | None = None
    slide_count: int | None = None
    has_thumbnails: bool = False
    added_at: str = Field(default_factory=now_iso)


class SourcesDoc(Doc):
    KIND: ClassVar[str] = "sources"
    items: list[SourceMeta] = Field(default_factory=list)


MapStatus = Literal["none", "queued", "running", "ready", "failed"]


class Lecture(Doc):
    KIND: ClassVar[str] = "lecture"
    id: str = Field(default_factory=new_id)
    course_id: str
    title: str
    order: int = 0
    source_ids: list[str] = Field(default_factory=list)
    map_status: MapStatus = "none"
    map_job_id: str | None = None
    map_error: str | None = None
    map_fallback: bool = False
    map_warnings: list[str] = Field(default_factory=list)
    uncovered_slides: list[SlideRef] = Field(default_factory=list)
    created_at: str = Field(default_factory=now_iso)


# --------------------------------------------------------------------------- map

class Node(Model):
    id: str = Field(default_factory=new_id)
    label: str
    parent_id: str | None = None
    children: list[str] = Field(default_factory=list)
    sources: list[SlideRef] = Field(default_factory=list)
    status: Status = "not_started"
    status_mode: StatusMode = "auto"  # performance-driven once there are results (SPEC §5.14)
    last_studied_at: str | None = None
    origin: Literal["ai", "user"] = "ai"
    collapsed: bool = False


class MapDoc(Doc):
    KIND: ClassVar[str] = "map"
    VERSION: ClassVar[int] = 2  # v2: status_mode defaults to "auto" (see core/migrations.py)
    lecture_id: str
    root_id: str
    nodes: dict[str, Node] = Field(default_factory=dict)


# --------------------------------------------------------------------------- slides (derived cache)

class Slide(Model):
    number: int
    text: str = ""
    has_images: bool = False


class SlidesDoc(Doc):
    KIND: ClassVar[str] = "slides"
    source_id: str
    slides: list[Slide] = Field(default_factory=list)


# --------------------------------------------------------------------------- threads

MessageRole = Literal["user", "assistant"]
MessageKind = Literal["question", "try_first", "attempt", "answer", "hint"]


class Message(Model):
    role: MessageRole
    kind: MessageKind
    content: str


class Exchange(Model):
    id: str = Field(default_factory=new_id)
    kept_at: str | None = None
    created_at: str = Field(default_factory=now_iso)
    messages: list[Message] = Field(default_factory=list)


class ThreadsDoc(Doc):
    KIND: ClassVar[str] = "threads"
    by_node: dict[str, list[Exchange]] = Field(default_factory=dict)


class RecentExchange(Exchange):
    node_id: str
    expires_at: str


class RecentDoc(Doc):
    KIND: ClassVar[str] = "recent"
    items: list[RecentExchange] = Field(default_factory=list)


# --------------------------------------------------------------------------- notes / inbox

class Note(Model):
    id: str = Field(default_factory=new_id)
    text: str
    node_id: str | None = None
    pinned_from: str | None = None  # exchange id if pinned from a thread
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class NotesDoc(Doc):
    KIND: ClassVar[str] = "notes"
    items: list[Note] = Field(default_factory=list)


class NoteDestination(Model):
    course_id: str | None = None
    lecture_id: str | None = None
    node_id: str | None = None
    label: str = ""


class InboxItem(Model):
    id: str = Field(default_factory=new_id)
    text: str
    created_at: str = Field(default_factory=now_iso)
    suggestion: NoteDestination | None = None


class InboxDoc(Doc):
    KIND: ClassVar[str] = "inbox"
    items: list[InboxItem] = Field(default_factory=list)


# --------------------------------------------------------------------------- practice

class PracticeOrigin(Model):
    kind: Literal["node", "thread", "generate", "note"] = "generate"
    source_ids: list[str] = Field(default_factory=list)
    ref: str = ""


class PracticeItem(Model):
    id: str = Field(default_factory=new_id)
    type: Literal["card", "question"]
    node_id: str | None = None
    front: str
    back: str = ""
    answer_status: Literal["ai_unverified", "verified"] = "ai_unverified"
    origin: PracticeOrigin = Field(default_factory=PracticeOrigin)
    fsrs: dict[str, Any] | None = None
    created_at: str = Field(default_factory=now_iso)


class PracticeDoc(Doc):
    KIND: ClassVar[str] = "practice"
    items: list[PracticeItem] = Field(default_factory=list)


# --------------------------------------------------------------------------- results (jsonl rows)

class ResultRecord(Model):
    id: str = Field(default_factory=new_id)
    node_id: str
    kind: Literal["test_me", "recall", "explain"]
    score: float  # 0..1
    details: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now_iso)


# --------------------------------------------------------------------------- reminders

class ReminderLink(Model):
    kind: Literal["course", "lecture", "node"]
    id: str
    course_id: str | None = None
    lecture_id: str | None = None


class Reminder(Model):
    id: str = Field(default_factory=new_id)
    text: str
    due_at: str
    tags: list[str] = Field(default_factory=list)
    course_id: str | None = None
    link: ReminderLink | None = None
    done: bool = False
    created_at: str = Field(default_factory=now_iso)


class TagColour(Model):
    name: str
    colour: str  # token name, e.g. "tag-1"


class RemindersDoc(Doc):
    KIND: ClassVar[str] = "reminders"
    items: list[Reminder] = Field(default_factory=list)
    custom_tags: list[TagColour] = Field(default_factory=list)


# --------------------------------------------------------------------------- usage (jsonl rows)

class UsageEvent(Model):
    feature: str
    at: str = Field(default_factory=now_iso)
