"""Today screen data (SPEC §5.9, v0.1 parts)."""

from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel, Field

from backend.core.courses import list_courses, list_lectures
from backend.core.reminders import due, list_reminders, local_now
from backend.core.schemas import MapDoc, Reminder
from backend.core.storage import Storage


class WeakNode(BaseModel):
    course_id: str
    course_name: str
    lecture_id: str
    lecture_title: str
    node_id: str
    label: str


class LectureProgress(BaseModel):
    course_id: str
    course_name: str
    lecture_id: str
    title: str
    got_it: int = 0
    revising: int = 0
    confused: int = 0
    not_started: int = 0


class ExamCountdown(BaseModel):
    reminder: Reminder
    days: int


class FadingTopic(BaseModel):
    course_id: str
    lecture_id: str
    lecture_title: str
    node_id: str | None
    label: str
    count: int


class WeekSummary(BaseModel):
    focus_min: int = 0
    sessions: int = 0
    reviews: int = 0
    tests: int = 0
    topics_studied: int = 0


class TodayOut(BaseModel):
    has_courses: bool
    current_course_id: str | None = None
    weak_nodes: list[WeakNode] = Field(default_factory=list)
    progress: list[LectureProgress] = Field(default_factory=list)
    overdue: list[Reminder] = Field(default_factory=list)
    today: list[Reminder] = Field(default_factory=list)
    upcoming: list[Reminder] = Field(default_factory=list)
    exam: ExamCountdown | None = None
    due: int = 0
    fading: list[FadingTopic] = Field(default_factory=list)
    week: WeekSummary = Field(default_factory=WeekSummary)


def build_today(st: Storage, now: datetime | None = None) -> TodayOut:
    now = now or local_now()
    courses = list_courses(st)
    out = TodayOut(has_courses=bool(courses))
    for c in courses:
        for lec in list_lectures(st, c.id):
            path = st.paths.map(c.id, lec.id)
            if not st.exists(path):
                continue
            doc = st.read_doc(path, MapDoc)
            prog = LectureProgress(course_id=c.id, course_name=c.name, lecture_id=lec.id, title=lec.title)
            for n in doc.nodes.values():
                if n.id == doc.root_id:
                    continue
                setattr(prog, n.status, getattr(prog, n.status) + 1)
                if n.status == "confused":
                    out.weak_nodes.append(WeakNode(course_id=c.id, course_name=c.name, lecture_id=lec.id,
                                                   lecture_title=lec.title, node_id=n.id, label=n.label))
            out.progress.append(prog)

    end_today = now.replace(hour=23, minute=59, second=59, microsecond=0)
    start_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week = end_today + timedelta(days=7)
    items = sorted((r for r in list_reminders(st).items if not r.done), key=due)
    for r in items:
        d = due(r)
        if d < now:
            out.overdue.append(r)
        elif d <= end_today:
            out.today.append(r)
        elif d <= week:
            out.upcoming.append(r)
    # "current/last course": the most recently studied one, else the newest
    best: tuple[str, str] | None = None
    for c in courses:
        for lec in list_lectures(st, c.id):
            path = st.paths.map(c.id, lec.id)
            if st.exists(path):
                for n in st.read_doc(path, MapDoc).nodes.values():
                    if n.last_studied_at and (best is None or n.last_studied_at > best[0]):
                        best = (n.last_studied_at, c.id)
    out.current_course_id = best[1] if best else (courses[-1].id if courses else None)

    _review_parts(st, courses, now, out)

    exams = [r for r in items if "exam" in r.tags and due(r) >= start_today]
    if exams:
        nearest = exams[0]
        days = (due(nearest).date() - now.date()).days
        out.exam = ExamCountdown(reminder=nearest, days=days)
    return out


FADING_THRESHOLD = 0.85
FADING_WITHIN = timedelta(days=2)


class _Session(BaseModel):
    started_at: str
    ended_at: str
    work_min: int
    completed: bool = True


class _LogRow(BaseModel):
    reviewed_at: str


def _review_parts(st: Storage, courses: list, now: datetime, out: TodayOut) -> None:  # noqa: ANN001
    """v0.2 Today parts (SPEC §5.9): due count, fading soon, weekly summary."""
    from backend.core.review import all_items, is_due, retrievability
    from backend.core.schemas import ResultRecord

    soon = now + FADING_WITHIN
    fading: dict[tuple[str, str, str | None], FadingTopic] = {}
    week_ago = now - timedelta(days=7)
    for c in courses:
        for r in all_items(st, c.id):
            if is_due(r.item, now):
                out.due += 1
                continue
            p = retrievability(r.item, soon)
            if r.lecture_id and p is not None and p < FADING_THRESHOLD:
                key = (c.id, r.lecture_id, r.item.node_id)
                t = fading.get(key)
                if t is None:
                    t = FadingTopic(course_id=c.id, lecture_id=r.lecture_id, lecture_title=r.lecture_title,
                                    node_id=r.item.node_id, label=r.node_label or r.lecture_title, count=0)
                    fading[key] = t
                t.count += 1
        out.week.reviews += sum(
            1 for row in st.read_jsonl(st.paths.review_log(c.id), _LogRow) if datetime.fromisoformat(row.reviewed_at) >= week_ago
        )
        for lec in list_lectures(st, c.id):
            rows = [r for r in st.read_jsonl(st.paths.results(c.id, lec.id), ResultRecord)
                    if datetime.fromisoformat(r.created_at) >= week_ago]
            out.week.tests += len({(r.details.get("session_id") or r.id) for r in rows})
            path = st.paths.map(c.id, lec.id)
            if st.exists(path):
                out.week.topics_studied += sum(
                    1 for n in st.read_doc(path, MapDoc).nodes.values()
                    if n.last_studied_at and datetime.fromisoformat(n.last_studied_at) >= week_ago
                )
    out.fading = sorted(fading.values(), key=lambda t: -t.count)[:5]
    for s in st.read_jsonl(st.paths.sessions, _Session):
        try:
            end = datetime.fromisoformat(s.ended_at)
        except ValueError:
            continue
        if end.tzinfo is None:
            end = end.replace(tzinfo=now.tzinfo)
        if end >= week_ago:
            out.week.sessions += 1
            out.week.focus_min += s.work_min
