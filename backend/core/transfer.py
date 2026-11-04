"""Export / import a course as a zip (SPEC §5.15)."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import PurePosixPath

from backend.core.courses import get_course
from backend.core.ids import is_id, new_id
from backend.core.storage import Storage

MANIFEST = "nodebook-course.json"
MAX_IMPORT = 2 * 1024 * 1024 * 1024


class ImportError_(ValueError):
    pass


def export_course(st: Storage, course_id: str) -> bytes:
    get_course(st, course_id)
    root = st.paths.course_dir(course_id)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(MANIFEST, json.dumps({"schema": 1, "course_id": course_id}))
        for p in sorted(root.rglob("*")):
            if p.is_file() and not p.name.endswith(".tmp") and "derived" not in p.relative_to(root).parts:
                z.write(p, f"course/{p.relative_to(root).as_posix()}")
    return buf.getvalue()


def import_course(st: Storage, data: bytes) -> str:
    try:
        z = zipfile.ZipFile(io.BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise ImportError_("That isn't a Nodebook course export (.zip).") from exc
    with z:
        try:
            manifest = json.loads(z.read(MANIFEST))
        except KeyError as exc:
            raise ImportError_("That zip has no Nodebook course in it.") from exc
        old_id = str(manifest.get("course_id", ""))
        if not is_id(old_id):
            raise ImportError_("The course export is damaged.")
        total = sum(i.file_size for i in z.infolist())
        if total > MAX_IMPORT:
            raise ImportError_("That export is too large.")
        new = old_id if not st.exists(st.paths.course_dir(old_id)) else new_id()
        dest = st.paths.course_dir(new)
        for info in z.infolist():
            name = info.filename
            if info.is_dir() or not name.startswith("course/"):
                continue
            rel = PurePosixPath(name[len("course/"):])
            if rel.is_absolute() or ".." in rel.parts:
                raise ImportError_("The course export contains unsafe paths.")
            target = st.paths.check(dest / rel)  # rejects anything outside the data folder
            raw = z.read(info)
            if new != old_id and target.suffix == ".json":
                raw = raw.replace(old_id.encode(), new.encode())
            st.write_bytes_atomic(target, raw)
    return new
