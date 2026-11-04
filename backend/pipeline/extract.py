"""Extract a source once and cache the result in the derived folder."""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path

from backend.core.courses import update_source
from backend.core.schemas import Slide, SlidesDoc, SourceMeta
from backend.core.storage import Storage
from backend.pipeline.parse_pdf import ParseError, parse_pdf
from backend.pipeline.parse_pptx import parse_pptx, pptx_to_pdf

PageProgress = Callable[[int, int], None]


def _parse_text(path: Path) -> list[Slide]:
    text = path.read_text("utf-8", errors="replace")
    blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    pages: list[str] = []
    cur = ""
    for b in blocks:
        if len(cur) + len(b) > 1200 and cur:
            pages.append(cur)
            cur = ""
        cur = (cur + "\n\n" + b).strip()
    if cur:
        pages.append(cur)
    return [Slide(number=i + 1, text=t) for i, t in enumerate(pages)]


def extract_source(
    st: Storage, course_id: str, meta: SourceMeta, on_page: PageProgress | None = None, force: bool = False
) -> SlidesDoc:
    cache = st.paths.slides_json(course_id, meta.id)
    if not force and st.exists(cache):
        return st.read_doc(cache, SlidesDoc)
    src = st.paths.source_file(course_id, meta.id, meta.ext)
    if not st.exists(src):
        raise ParseError("The source file is missing from the data folder.")

    def write_thumb(n: int, png: bytes) -> None:
        st.write_bytes_atomic(st.paths.thumbnail(course_id, meta.id, n), png)

    has_thumbs = False
    if meta.ext == "pdf":
        slides = parse_pdf(src, write_thumb=write_thumb, on_page=on_page)
        has_thumbs = True
    elif meta.ext == "pptx":
        slides = parse_pptx(src)
        pdf = pptx_to_pdf(src)
        if pdf:
            with tempfile.TemporaryDirectory(prefix="nodebook-") as tmp:
                p = Path(tmp) / "deck.pdf"
                p.write_bytes(pdf)
                try:
                    pages = parse_pdf(p, write_thumb=write_thumb, on_page=on_page)
                    has_thumbs = len(pages) == len(slides)
                except ParseError:
                    has_thumbs = False
    elif meta.ext in ("txt", "md"):
        slides = _parse_text(src)
    else:
        raise ParseError(f"Can't read .{meta.ext} files.")

    doc = SlidesDoc(source_id=meta.id, slides=slides)
    st.write_doc(cache, doc)
    update_source(st, course_id, meta.id, slide_count=len(slides), has_thumbnails=has_thumbs)
    return doc


__all__ = ["extract_source", "ParseError"]
