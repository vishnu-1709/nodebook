"""PDF → per-page text, has-images flag, PNG thumbnails (~1000 px wide)."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pymupdf

from backend.core.schemas import Slide

THUMB_WIDTH = 1000

ThumbWriter = Callable[[int, bytes], None]


class ParseError(RuntimeError):
    pass


def _clean(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines()]
    return "\n".join(ln for ln in lines if ln)


def parse_pdf(
    path: Path,
    write_thumb: ThumbWriter | None = None,
    on_page: Callable[[int, int], None] | None = None,
) -> list[Slide]:
    try:
        doc = pymupdf.open(path)
    except Exception as exc:  # noqa: BLE001
        raise ParseError(f"Couldn't open this PDF: {exc}") from exc
    if doc.needs_pass:
        raise ParseError("This PDF is password-protected.")
    slides: list[Slide] = []
    try:
        total = len(doc)
        for i, page in enumerate(doc):
            text = _clean(page.get_text("text"))
            has_images = bool(page.get_images(full=False))
            if not has_images and len(text) < 40:
                has_images = len(page.get_drawings()) > 3  # vector figure with little text
            slides.append(Slide(number=i + 1, text=text, has_images=has_images))
            if write_thumb is not None:
                zoom = THUMB_WIDTH / max(page.rect.width, 1)
                pix = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False)
                write_thumb(i + 1, pix.tobytes("png"))
            if on_page:
                on_page(i + 1, total)
    finally:
        doc.close()
    if slides and not any(s.text for s in slides):
        raise ParseError(
            "No text found in this PDF. It may be scanned images — OCR isn't supported yet."
        )
    return slides
