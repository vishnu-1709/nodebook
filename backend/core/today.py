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


class TodayOut(BaseModel):
    has_courses: bool
    current_course_id: str | None = None
    weak_nodes: list[WeakNode] = Field(default_factory=list)
    progress: list[LectureProgress] = Field(default_factory=list)
    overdue: list[Reminder] = Field(default_factory=list)
    today: list[Reminder] = Field(default_factory=list)
    upcoming: list[Reminder] = Field(default_factory=list)
    exam: ExamCountdown | None = None


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

    exams = [r for r in items if "exam" in r.tags and due(r) >= start_today]
    if exams:
        nearest = exams[0]
        days = (due(nearest).date() - now.date()).days
        out.exam = ExamCountdown(reminder=nearest, days=days)
    return out
