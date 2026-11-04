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


# --------------------------------------------------------------------------- sources

from typing import BinaryIO  # noqa: E402

from backend.core.schemas import SourceKind, SourceMeta  # noqa: E402

ALLOWED_EXT = {"pdf", "pptx", "txt", "md"}
LECTURE_EXT = {"pdf", "pptx"}
MAX_UPLOAD = 250 * 1024 * 1024


class BadUpload(ValueError):
    pass


def file_ext(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def list_sources(st: Storage, course_id: str) -> list[SourceMeta]:
    get_course(st, course_id)
    return st.read_doc(st.paths.sources_meta(course_id), SourcesDoc, SourcesDoc).items


def get_source(st: Storage, course_id: str, source_id: str) -> SourceMeta:
    for s in list_sources(st, course_id):
        if s.id == source_id:
            return s
    raise NotFound("source not found")


def add_source(
    st: Storage, course_id: str, filename: str, stream: BinaryIO, kind: SourceKind = "slides",
    lecture_id: str | None = None,
) -> SourceMeta:
    get_course(st, course_id)
    ext = file_ext(filename)
    if ext not in ALLOWED_EXT:
        raise BadUpload(f"Unsupported file type .{ext or '?'} — use PDF, PPTX, TXT or MD.")
    meta = SourceMeta(filename=filename, ext=ext, kind=kind, lecture_id=lecture_id)
    path = st.paths.source_file(course_id, meta.id, ext)
    try:
        meta.size = st.write_stream(path, stream, max_bytes=MAX_UPLOAD)
    except ValueError as exc:
        raise BadUpload("File is larger than 250 MB.") from exc
    with st.update_doc(st.paths.sources_meta(course_id), SourcesDoc, SourcesDoc) as doc:
        doc.items.append(meta)
    return meta


def update_source(st: Storage, course_id: str, source_id: str, **fields: object) -> SourceMeta:
    with st.update_doc(st.paths.sources_meta(course_id), SourcesDoc, SourcesDoc) as doc:
        for s in doc.items:
            if s.id == source_id:
                for k, v in fields.items():
                    setattr(s, k, v)
                return s
    raise NotFound("source not found")


def delete_source(st: Storage, course_id: str, source_id: str) -> None:
    meta = get_source(st, course_id, source_id)
    st.delete_file(st.paths.source_file(course_id, source_id, meta.ext))
    st.delete_tree(st.paths.derived_dir(course_id, source_id))
    with st.update_doc(st.paths.sources_meta(course_id), SourcesDoc, SourcesDoc) as doc:
        doc.items = [s for s in doc.items if s.id != source_id]


# --------------------------------------------------------------------------- lectures

def lecture_title_from_filename(filename: str) -> str:
    stem = filename.rsplit(".", 1)[0]
    stem = stem.replace("_", " ").replace("-", " ")
    title = " ".join(stem.split())
    return (title[:1].upper() + title[1:]) if title else "Untitled lecture"


def create_lecture(st: Storage, course_id: str, title: str, source_ids: list[str]) -> Lecture:
    get_course(st, course_id)
    lec = Lecture(course_id=course_id, title=title.strip() or "Untitled lecture", source_ids=source_ids)
    st.write_doc(st.paths.lecture(course_id, lec.id), lec)
    with st.update_doc(st.paths.course(course_id), Course) as c:
        c.lecture_order.append(lec.id)
        lec.order = len(c.lecture_order) - 1
    return lec


def update_lecture(st: Storage, course_id: str, lecture_id: str, **fields: object) -> Lecture:
    get_lecture(st, course_id, lecture_id)
    with st.update_doc(st.paths.lecture(course_id, lecture_id), Lecture) as lec:
        for k, v in fields.items():
            setattr(lec, k, v)
    return lec


def reorder_lectures(st: Storage, course_id: str, order: list[str]) -> list[Lecture]:
    current = {l.id for l in list_lectures(st, course_id)}
    if set(order) != current or len(order) != len(current):
        raise BadUpload("Order must list every lecture exactly once.")
    with st.update_doc(st.paths.course(course_id), Course) as c:
        c.lecture_order = list(order)
    return list_lectures(st, course_id)


def delete_lecture(st: Storage, course_id: str, lecture_id: str) -> None:
    lec = get_lecture(st, course_id, lecture_id)
    st.delete_tree(st.paths.lecture_dir(course_id, lecture_id))
    with st.update_doc(st.paths.course(course_id), Course) as c:
        c.lecture_order = [x for x in c.lecture_order if x != lecture_id]
    # sources stay on the course shelf; just unlink them
    for sid in lec.source_ids:
        try:
            update_source(st, course_id, sid, lecture_id=None)
        except NotFound:
            pass
