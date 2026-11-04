from __future__ import annotations

from pathlib import Path

import pymupdf
import pytest

from backend.pipeline.parse_pdf import ParseError, parse_pdf
from backend.pipeline.parse_pptx import parse_pptx

DECKS = Path(__file__).resolve().parent.parent / "fixtures" / "decks"


def test_pdf_text_numbers_images_and_thumbs() -> None:
    thumbs: dict[int, bytes] = {}
    slides = parse_pdf(DECKS / "linear_regression.pdf", write_thumb=lambda n, b: thumbs.__setitem__(n, b))
    assert len(slides) == 25
    assert [s.number for s in slides] == list(range(1, 26))
    assert slides[4].text.startswith("The linear model")
    assert "ŷ = wᵀx + b" in slides[4].text
    assert slides[22].has_images and len(slides[22].text) < 20
    assert not slides[4].has_images
    assert len(thumbs) == 25 and thumbs[1][:4] == b"\x89PNG"
    pix = pymupdf.Pixmap(thumbs[1])
    assert 990 <= pix.width <= 1010


def test_pdf_without_text_is_rejected(tmp_path: Path) -> None:
    doc = pymupdf.open()
    doc.new_page()
    p = tmp_path / "scan.pdf"
    doc.save(p)
    with pytest.raises(ParseError, match="OCR"):
        parse_pdf(p)


def test_pdf_garbage_is_rejected(tmp_path: Path) -> None:
    p = tmp_path / "bad.pdf"
    p.write_bytes(b"not a pdf")
    with pytest.raises(ParseError):
        parse_pdf(p)


def test_pptx_text_tables_images() -> None:
    slides = parse_pptx(DECKS / "sorting.pptx")
    assert len(slides) == 10
    assert slides[0].text.splitlines()[0] == "Sorting Algorithms"
    assert "Merge | O(n log n) | O(n log n)" in slides[6].text
    assert slides[8].has_images and slides[8].text == ""
    assert slides[4].text.startswith("Merge sort")
