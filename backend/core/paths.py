"""Data-folder layout. Every path the app touches is built here and checked to
stay inside the data folder (SPEC §3)."""

from __future__ import annotations

import re
from pathlib import Path

from backend.core.ids import is_id

_EXT_RE = re.compile(r"^[a-z0-9]{1,8}$")


class PathError(ValueError):
    """Raised when a path would escape the data folder or an id is malformed."""


class DataPaths:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root).expanduser().resolve()

    # -- guard -----------------------------------------------------------------
    def check(self, path: Path | str) -> Path:
        p = Path(path)
        if not p.is_absolute():
            p = self.root / p
        resolved = p.resolve()
        if resolved != self.root and self.root not in resolved.parents:
            raise PathError(f"path outside data folder: {path}")
        return resolved

    @staticmethod
    def _id(value: str) -> str:
        if not is_id(value):
            raise PathError(f"invalid id: {value!r}")
        return value

    # -- top level -------------------------------------------------------------
    @property
    def inbox(self) -> Path:
        return self.check(self.root / "inbox.json")

    @property
    def reminders(self) -> Path:
        return self.check(self.root / "reminders.json")

    @property
    def sessions(self) -> Path:
        return self.check(self.root / "sessions.jsonl")

    @property
    def usage(self) -> Path:
        return self.check(self.root / "usage.jsonl")

    @property
    def courses_dir(self) -> Path:
        return self.check(self.root / "courses")

    # -- course ----------------------------------------------------------------
    def course_dir(self, course_id: str) -> Path:
        return self.check(self.courses_dir / self._id(course_id))

    def course(self, course_id: str) -> Path:
        return self.course_dir(course_id) / "course.json"

    def sources_dir(self, course_id: str) -> Path:
        return self.course_dir(course_id) / "sources"

    def sources_meta(self, course_id: str) -> Path:
        return self.sources_dir(course_id) / "sources.json"

    def source_file(self, course_id: str, source_id: str, ext: str) -> Path:
        ext = ext.lower().lstrip(".")
        if not _EXT_RE.match(ext):
            raise PathError(f"invalid extension: {ext!r}")
        return self.check(self.sources_dir(course_id) / f"{self._id(source_id)}.{ext}")

    def derived_dir(self, course_id: str, source_id: str) -> Path:
        """Cache of extracted slide text + thumbnails for a source (rebuildable)."""
        return self.check(self.course_dir(course_id) / "derived" / self._id(source_id))

    def slides_json(self, course_id: str, source_id: str) -> Path:
        return self.derived_dir(course_id, source_id) / "slides.json"

    def thumbnail(self, course_id: str, source_id: str, slide: int) -> Path:
        return self.derived_dir(course_id, source_id) / f"slide-{int(slide):04d}.png"

    def course_notes(self, course_id: str) -> Path:
        return self.course_dir(course_id) / "notes.json"

    def course_practice(self, course_id: str) -> Path:
        """Practice items saved at course level (no node fits)."""
        return self.course_dir(course_id) / "practice.json"

    def review_log(self, course_id: str) -> Path:
        return self.course_dir(course_id) / "review_log.jsonl"

    # -- lecture ---------------------------------------------------------------
    def lectures_dir(self, course_id: str) -> Path:
        return self.course_dir(course_id) / "lectures"

    def lecture_dir(self, course_id: str, lecture_id: str) -> Path:
        return self.check(self.lectures_dir(course_id) / self._id(lecture_id))

    def lecture(self, course_id: str, lecture_id: str) -> Path:
        return self.lecture_dir(course_id, lecture_id) / "lecture.json"

    def map(self, course_id: str, lecture_id: str) -> Path:
        return self.lecture_dir(course_id, lecture_id) / "map.json"

    def threads(self, course_id: str, lecture_id: str) -> Path:
        return self.lecture_dir(course_id, lecture_id) / "threads.json"

    def recent(self, course_id: str, lecture_id: str) -> Path:
        return self.lecture_dir(course_id, lecture_id) / "recent.json"

    def lecture_notes(self, course_id: str, lecture_id: str) -> Path:
        return self.lecture_dir(course_id, lecture_id) / "notes.json"

    def practice(self, course_id: str, lecture_id: str) -> Path:
        return self.lecture_dir(course_id, lecture_id) / "practice.json"

    def results(self, course_id: str, lecture_id: str) -> Path:
        return self.lecture_dir(course_id, lecture_id) / "results.jsonl"
