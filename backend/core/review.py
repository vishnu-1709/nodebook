"""Spaced review with FSRS (SPEC §5.12). Cards and saved questions share one queue.

Each PracticeItem.fsrs holds `fsrs.Card.to_dict()`; None means "new" (due now).
Every rating appends to courses/<id>/review_log.jsonl."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from fsrs import Card, Rating, Scheduler
from pydantic import BaseModel, Field

from backend.core.clock import now
from backend.core.courses import NotFound, get_course, list_courses, list_lectures
from backend.core.schemas import MapDoc, PracticeDoc, PracticeItem
from backend.core.storage import Storage

RatingNum = Literal[1, 2, 3, 4]


def scheduler() -> Scheduler:
    return Scheduler()


def card_of(item: PracticeItem) -> Card:
    if item.fsrs:
        return Card.from_dict(item.fsrs)  # type: ignore[arg-type]
    c = Card()
    c.due = now()
    return c


def due_at(item: PracticeItem) -> datetime:
    if not item.fsrs:
        return datetime.min.replace(tzinfo=timezone.utc)
    return card_of(item).due


def is_due(item: PracticeItem, at: datetime | None = None) -> bool:
    return due_at(item) <= (at or now())


def fmt_interval(delta: timedelta) -> str:
    s = delta.total_seconds()
    if s < 60 * 10:
        return "<10m"
    if s < 3600:
        return f"{round(s / 60)}m"
    if s < 86400:
        return f"{round(s / 3600)}h"
    d = s / 86400
    if d < 30:
        return f"{round(d)}d"
    if d < 365:
        return f"{round(d / 30)}mo"
    return f"{d / 365:.1f}y"


def intervals(item: PracticeItem, at: datetime | None = None) -> dict[str, str]:
    at = at or now()
    sch = scheduler()
    out: dict[str, str] = {}
    for r in Rating:
        c, _ = sch.review_card(card_of(item), r, review_datetime=at)
        out[str(int(r))] = fmt_interval(c.due - at)
    return out


class ReviewItem(BaseModel):
    item: PracticeItem
    course_id: str
    lecture_id: str | None
    lecture_title: str
    node_label: str = ""
    node_path: list[str] = Field(default_factory=list)
    node_status: str = ""
    intervals: dict[str, str] = Field(default_factory=dict)


class ReviewLogRow(BaseModel):
    item_id: str
    lecture_id: str | None
    node_id: str | None
    rating: int
    reviewed_at: str
    duration_ms: int | None = None
    due_before: str | None = None
    due_after: str
    state_after: int


def _path(doc: MapDoc | None, node_id: str | None) -> list[str]:
    if not doc or not node_id:
        return []
    out: list[str] = []
    cur = doc.nodes.get(node_id)
    seen: set[str] = set()
    while cur is not None and cur.id not in seen:
        seen.add(cur.id)
        out.insert(0, cur.label)
        cur = doc.nodes.get(cur.parent_id) if cur.parent_id else None
    return out[1:] if len(out) > 1 else out  # drop the root (= lecture title)


def all_items(st: Storage, course_id: str, lecture_id: str | None = None) -> list[ReviewItem]:
    get_course(st, course_id)
    out: list[ReviewItem] = []
    if lecture_id is None:
        for it in st.read_doc(st.paths.course_practice(course_id), PracticeDoc, PracticeDoc).items:
            out.append(ReviewItem(item=it, course_id=course_id, lecture_id=None, lecture_title="Course"))
    for lec in list_lectures(st, course_id):
        if lecture_id and lec.id != lecture_id:
            continue
        mp = st.paths.map(course_id, lec.id)
        doc = st.read_doc(mp, MapDoc) if st.exists(mp) else None
        for it in st.read_doc(st.paths.practice(course_id, lec.id), PracticeDoc, PracticeDoc).items:
            node = doc.nodes.get(it.node_id) if doc and it.node_id else None
            out.append(ReviewItem(item=it, course_id=course_id, lecture_id=lec.id, lecture_title=lec.title,
                                  node_label=node.label if node else "", node_path=_path(doc, it.node_id),
                                  node_status=node.status if node else ""))
    return out


def queue(st: Storage, course_id: str | None = None, lecture_id: str | None = None,
          at: datetime | None = None) -> list[ReviewItem]:
    """Due items, overdue first (by due date), then new ones in creation order."""
    at = at or now()
    courses = [course_id] if course_id else [c.id for c in list_courses(st)]
    due: list[ReviewItem] = []
    for cid in courses:
        due.extend(r for r in all_items(st, cid, lecture_id if course_id else None) if is_due(r.item, at))
    due.sort(key=lambda r: (r.item.fsrs is None, due_at(r.item) if r.item.fsrs else r.item.created_at))
    for r in due:
        r.intervals = intervals(r.item, at)
    return due


def due_counts(st: Storage, at: datetime | None = None) -> dict[str, int]:
    at = at or now()
    return {c.id: sum(1 for r in all_items(st, c.id) if is_due(r.item, at)) for c in list_courses(st)}


def rate(st: Storage, course_id: str, lecture_id: str | None, item_id: str, rating: RatingNum,
         duration_ms: int | None = None, at: datetime | None = None) -> PracticeItem:
    at = at or now()
    path = st.paths.practice(course_id, lecture_id) if lecture_id else st.paths.course_practice(course_id)
    with st.update_doc(path, PracticeDoc, PracticeDoc) as doc:
        item = next((i for i in doc.items if i.id == item_id), None)
        if item is None:
            raise NotFound("review item not found")
        before = card_of(item).due.isoformat() if item.fsrs else None
        card, _ = scheduler().review_card(card_of(item), Rating(rating), review_datetime=at)
        item.fsrs = card.to_dict()
        result = item.model_copy(deep=True)
    st.append_jsonl(st.paths.review_log(course_id), ReviewLogRow(
        item_id=item_id, lecture_id=lecture_id, node_id=result.node_id, rating=int(rating),
        reviewed_at=at.isoformat(), duration_ms=duration_ms, due_before=before,
        due_after=card.due.isoformat(), state_after=int(card.state),
    ))
    return result


def retrievability(item: PracticeItem, at: datetime) -> float | None:
    if not item.fsrs:
        return None
    return float(scheduler().get_card_retrievability(card_of(item), current_datetime=at))
