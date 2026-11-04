"""PPTX → per-slide text + has-images flag. Thumbnails only if LibreOffice is
installed (convert PPTX → PDF, then render with PyMuPDF)."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Iterable
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.shapes.base import BaseShape

from backend.core.schemas import Slide
from backend.pipeline.parse_pdf import ParseError


def _walk(shapes: Iterable[BaseShape]) -> Iterable[BaseShape]:
    for sh in shapes:
        if sh.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _walk(sh.shapes)  # type: ignore[attr-defined]
        else:
            yield sh


def _shape_text(sh: BaseShape) -> list[str]:
    out: list[str] = []
    if getattr(sh, "has_text_frame", False) and sh.has_text_frame:  # type: ignore[attr-defined]
        for p in sh.text_frame.paragraphs:  # type: ignore[attr-defined]
            t = "".join(r.text for r in p.runs).strip()
            if t:
                out.append(t)
    if getattr(sh, "has_table", False) and sh.has_table:  # type: ignore[attr-defined]
        for row in sh.table.rows:  # type: ignore[attr-defined]
            cells = [c.text.strip() for c in row.cells]
            if any(cells):
                out.append(" | ".join(cells))
    return out


def _is_image(sh: BaseShape) -> bool:
    if sh.shape_type == MSO_SHAPE_TYPE.PICTURE:
        return True
    if getattr(sh, "is_placeholder", False):
        try:
            return hasattr(sh, "image")
        except Exception:  # noqa: BLE001
            return False
    return sh.shape_type in (MSO_SHAPE_TYPE.CHART, MSO_SHAPE_TYPE.MEDIA)


def parse_pptx(path: Path) -> list[Slide]:
    try:
        prs = Presentation(str(path))
    except Exception as exc:  # noqa: BLE001
        raise ParseError(f"Couldn't open this PowerPoint file: {exc}") from exc
    slides: list[Slide] = []
    for i, slide in enumerate(prs.slides):
        lines: list[str] = []
        has_images = False
        # Title first so the first line is the slide title.
        title = slide.shapes.title
        if title is not None and title.has_text_frame and title.text_frame.text.strip():
            lines.append(title.text_frame.text.strip())
        for sh in _walk(slide.shapes):
            if title is not None and sh.shape_id == title.shape_id:
                continue
            lines.extend(_shape_text(sh))
            has_images = has_images or _is_image(sh)
        slides.append(Slide(number=i + 1, text="\n".join(lines), has_images=has_images))
    if not slides:
        raise ParseError("This PowerPoint file has no slides.")
    return slides


def find_libreoffice() -> str | None:
    for name in ("soffice", "libreoffice"):
        p = shutil.which(name)
        if p:
            return p
    for cand in (
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    ):
        if Path(cand).exists():
            return cand
    return None


def pptx_to_pdf(path: Path, timeout: float = 180.0) -> bytes | None:
    """Convert with LibreOffice if available. Returns PDF bytes or None."""
    soffice = find_libreoffice()
    if soffice is None:
        return None
    with tempfile.TemporaryDirectory(prefix="nodebook-lo-") as tmp:
        src = Path(tmp) / ("deck" + path.suffix.lower())
        shutil.copyfile(path, src)
        profile = Path(tmp) / "profile"
        try:
            subprocess.run(
                [soffice, f"-env:UserInstallation=file://{profile.as_posix()}", "--headless",
                 "--convert-to", "pdf", "--outdir", tmp, str(src)],
                check=True, timeout=timeout, capture_output=True,
            )
        except (subprocess.SubprocessError, OSError):
            return None
        out = Path(tmp) / "deck.pdf"
        return out.read_bytes() if out.exists() else None
