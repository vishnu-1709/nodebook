"""Notes (SPEC §5.7): node / lecture notes in lectures/<id>/notes.json, course
notes in courses/<id>/notes.json, unsorted quick notes in inbox.json."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from backend.core.clock import now_iso
from backend.core.courses import NotFound, get_course, get_lecture
from backend.core.schemas import InboxDoc, InboxItem, Note, NoteDestination, NotesDoc
from backend.core.storage import Storage

Where = Literal["node", "lecture", "course", "inbox"]


class Captured(BaseModel):
    where: Where
    note: Note | None = None
    inbox_item: InboxItem | None = None


def _path(st: Storage, course_id: str, lecture_id: str | None):  # noqa: ANN202
    return st.paths.lecture_notes(course_id, lecture_id) if lecture_id else st.paths.course_notes(course_id)


def list_notes(st: Storage, course_id: str, lecture_id: str | None = None, node_id: str | None = None) -> list[Note]:
    items = st.read_doc(_path(st, course_id, lecture_id), NotesDoc, NotesDoc).items
    if node_id is not None:
        items = [n for n in items if n.node_id == node_id]
    return items


def add_note(st: Storage, course_id: str, lecture_id: str | None, text: str, node_id: str | None = None) -> Note:
    get_course(st, course_id)
    if lecture_id:
        get_lecture(st, course_id, lecture_id)
    note = Note(text=text.strip(), node_id=node_id if lecture_id else None)
    with st.update_doc(_path(st, course_id, lecture_id), NotesDoc, NotesDoc) as doc:
        doc.items.append(note)
    return note


def update_note(st: Storage, course_id: str, lecture_id: str | None, note_id: str, text: str) -> Note:
    with st.update_doc(_path(st, course_id, lecture_id), NotesDoc, NotesDoc) as doc:
        for n in doc.items:
            if n.id == note_id:
                n.text = text.strip()
                n.updated_at = now_iso()
                return n
    raise NotFound("note not found")


def delete_note(st: Storage, course_id: str, lecture_id: str | None, note_id: str) -> None:
    with st.update_doc(_path(st, course_id, lecture_id), NotesDoc, NotesDoc) as doc:
        before = len(doc.items)
        doc.items = [n for n in doc.items if n.id != note_id]
        if len(doc.items) == before:
            raise NotFound("note not found")


def capture(st: Storage, text: str, course_id: str | None, lecture_id: str | None, node_id: str | None) -> Captured:
    """Save to the deepest context available (node > lecture > course); else inbox."""
    if course_id:
        note = add_note(st, course_id, lecture_id, text, node_id)
        where: Where = "node" if (lecture_id and node_id) else "lecture" if lecture_id else "course"
        return Captured(where=where, note=note)
    item = InboxItem(text=text.strip())
    with st.update_doc(st.paths.inbox, InboxDoc, InboxDoc) as doc:
        doc.items.append(item)
    return Captured(where="inbox", inbox_item=item)


def list_inbox(st: Storage) -> list[InboxItem]:
    return st.read_doc(st.paths.inbox, InboxDoc, InboxDoc).items


def set_suggestion(st: Storage, item_id: str, dest: NoteDestination | None) -> InboxItem:
    with st.update_doc(st.paths.inbox, InboxDoc, InboxDoc) as doc:
        for it in doc.items:
            if it.id == item_id:
                it.suggestion = dest
                return it
    raise NotFound("inbox item not found")


def file_item(st: Storage, item_id: str, dest: NoteDestination) -> Captured:
    if not dest.course_id:
        raise NotFound("Pick a course to file this note into.")
    items = list_inbox(st)
    item = next((i for i in items if i.id == item_id), None)
    if item is None:
        raise NotFound("inbox item not found")
    res = capture(st, item.text, dest.course_id, dest.lecture_id, dest.node_id)
    with st.update_doc(st.paths.inbox, InboxDoc, InboxDoc) as doc:
        doc.items = [i for i in doc.items if i.id != item_id]
    return res


def delete_inbox_item(st: Storage, item_id: str) -> None:
    with st.update_doc(st.paths.inbox, InboxDoc, InboxDoc) as doc:
        doc.items = [i for i in doc.items if i.id != item_id]
