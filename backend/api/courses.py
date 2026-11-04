from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.api.deps import get_ctx
from backend.core import courses as svc
from backend.core.context import AppContext
from backend.core.schemas import Course, Lecture, MapDoc, Note, NotesDoc, PracticeDoc, PracticeItem
from backend.core.usage import log_usage

router = APIRouter(prefix="/courses", tags=["courses"])


class CourseIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class StatusCounts(BaseModel):
    got_it: int = 0
    revising: int = 0
    confused: int = 0
    not_started: int = 0
    total: int = 0


class CourseDetail(BaseModel):
    course: Course
    lectures: list[Lecture]
    progress: dict[str, StatusCounts] = {}


class SavedPractice(BaseModel):
    item: PracticeItem
    lecture_id: str | None
    lecture_title: str
    node_label: str


class SavedNote(BaseModel):
    note: Note
    lecture_id: str | None
    lecture_title: str
    node_label: str


class SavedOut(BaseModel):
    practice: list[SavedPractice]
    notes: list[SavedNote]


def _progress(ctx: AppContext, course_id: str, lectures: list[Lecture]) -> dict[str, StatusCounts]:
    st = ctx.storage
    out: dict[str, StatusCounts] = {}
    for lec in lectures:
        path = st.paths.map(course_id, lec.id)
        if not st.exists(path):
            continue
        doc = st.read_doc(path, MapDoc)
        c = StatusCounts()
        for n in doc.nodes.values():
            if n.id == doc.root_id:
                continue
            setattr(c, n.status, getattr(c, n.status) + 1)
            c.total += 1
        out[lec.id] = c
    return out


@router.get("")
def list_courses(ctx: AppContext = Depends(get_ctx)) -> list[Course]:
    return svc.list_courses(ctx.storage)


@router.post("", status_code=201)
def create_course(body: CourseIn, ctx: AppContext = Depends(get_ctx)) -> Course:
    log_usage(ctx, "course.create")
    return svc.create_course(ctx.storage, body.name)


@router.get("/{course_id}")
def get_course(course_id: str, ctx: AppContext = Depends(get_ctx)) -> CourseDetail:
    lectures = svc.list_lectures(ctx.storage, course_id)
    return CourseDetail(
        course=svc.get_course(ctx.storage, course_id),
        lectures=lectures,
        progress=_progress(ctx, course_id, lectures),
    )


@router.get("/{course_id}/saved")
def saved(course_id: str, ctx: AppContext = Depends(get_ctx)) -> SavedOut:
    """Course "Saved" view: a query over practice.json + notes (SPEC §3), not a copy."""
    st = ctx.storage
    svc.get_course(st, course_id)
    out = SavedOut(practice=[], notes=[])
    for it in st.read_doc(st.paths.course_practice(course_id), PracticeDoc, PracticeDoc).items:
        out.practice.append(SavedPractice(item=it, lecture_id=None, lecture_title="Course", node_label=""))
    for n in st.read_doc(st.paths.course_notes(course_id), NotesDoc, NotesDoc).items:
        out.notes.append(SavedNote(note=n, lecture_id=None, lecture_title="Course", node_label=""))
    for lec in svc.list_lectures(st, course_id):
        labels: dict[str, str] = {}
        mp = st.paths.map(course_id, lec.id)
        if st.exists(mp):
            labels = {k: v.label for k, v in st.read_doc(mp, MapDoc).nodes.items()}
        for it in st.read_doc(st.paths.practice(course_id, lec.id), PracticeDoc, PracticeDoc).items:
            out.practice.append(SavedPractice(item=it, lecture_id=lec.id, lecture_title=lec.title,
                                              node_label=labels.get(it.node_id or "", "")))
        for n in st.read_doc(st.paths.lecture_notes(course_id, lec.id), NotesDoc, NotesDoc).items:
            out.notes.append(SavedNote(note=n, lecture_id=lec.id, lecture_title=lec.title,
                                       node_label=labels.get(n.node_id or "", "")))
    return out


@router.patch("/{course_id}")
def rename_course(course_id: str, body: CourseIn, ctx: AppContext = Depends(get_ctx)) -> Course:
    return svc.rename_course(ctx.storage, course_id, body.name)


@router.delete("/{course_id}", status_code=204)
def delete_course(course_id: str, ctx: AppContext = Depends(get_ctx)) -> None:
    svc.delete_course(ctx.storage, course_id)
