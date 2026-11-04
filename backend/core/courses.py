"""Course / lecture / source operations on top of Storage."""

from __future__ import annotations

from backend.core.schemas import Course, Lecture, SourcesDoc
from backend.core.storage import Storage


class NotFound(LookupError):
    pass


def list_courses(st: Storage) -> list[Course]:
    out = []
    for cid in st.list_dirs(st.paths.courses_dir):
        try:
            out.append(st.read_doc(st.paths.course(cid), Course))
        except (FileNotFoundError, ValueError):
            continue
    out.sort(key=lambda c: c.created_at)
    return out


def get_course(st: Storage, course_id: str) -> Course:
    try:
        return st.read_doc(st.paths.course(course_id), Course)
    except FileNotFoundError as exc:
        raise NotFound("course not found") from exc


def create_course(st: Storage, name: str) -> Course:
    course = Course(name=name.strip())
    st.write_doc(st.paths.course(course.id), course)
    st.write_doc(st.paths.sources_meta(course.id), SourcesDoc())
    return course


def rename_course(st: Storage, course_id: str, name: str) -> Course:
    get_course(st, course_id)
    with st.update_doc(st.paths.course(course_id), Course) as c:
        c.name = name.strip()
    return c


def delete_course(st: Storage, course_id: str) -> None:
    get_course(st, course_id)
    st.delete_tree(st.paths.course_dir(course_id))


def list_lectures(st: Storage, course_id: str) -> list[Lecture]:
    course = get_course(st, course_id)
    found: dict[str, Lecture] = {}
    for lid in st.list_dirs(st.paths.lectures_dir(course_id)):
        try:
            found[lid] = st.read_doc(st.paths.lecture(course_id, lid), Lecture)
        except (FileNotFoundError, ValueError):
            continue
    ordered = [found.pop(lid) for lid in course.lecture_order if lid in found]
    ordered.extend(sorted(found.values(), key=lambda l: l.created_at))
    for i, lec in enumerate(ordered):
        lec.order = i
    return ordered


def get_lecture(st: Storage, course_id: str, lecture_id: str) -> Lecture:
    try:
        return st.read_doc(st.paths.lecture(course_id, lecture_id), Lecture)
    except FileNotFoundError as exc:
        raise NotFound("lecture not found") from exc
