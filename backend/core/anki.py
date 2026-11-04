"""Anki export (SPEC §5.12) with genanki."""

from __future__ import annotations

import hashlib
import html
import tempfile
from pathlib import Path

import genanki

from backend.core.review import all_items

MODEL_ID = 1_607_392_319  # stable: same note type every export


def _stable_id(text: str) -> int:
    return int(hashlib.sha1(text.encode()).hexdigest()[:8], 16) | (1 << 30)


def _model() -> genanki.Model:
    return genanki.Model(
        MODEL_ID, "Nodebook basic",
        fields=[{"name": "Front"}, {"name": "Back"}, {"name": "Topic"}],
        templates=[{
            "name": "Card 1",
            "qfmt": "<div class=topic>{{Topic}}</div>{{Front}}",
            "afmt": "{{FrontSide}}<hr id=answer>{{Back}}",
        }],
        css=".card{font-family:'IBM Plex Sans',system-ui,sans-serif;font-size:20px;text-align:left;color:#16181D;background:#FFFFFF}"
            ".topic{font-size:13px;color:#5B616E;margin-bottom:12px}",
    )


def export_apkg(st, course_id: str, deck_name: str, lecture_id: str | None = None) -> bytes:  # noqa: ANN001
    items = all_items(st, course_id, lecture_id)
    if lecture_id is not None:
        items = [r for r in items if r.lecture_id == lecture_id]
    deck = genanki.Deck(_stable_id(f"{course_id}:{lecture_id or ''}"), deck_name)
    model = _model()
    for r in items:
        topic = " › ".join([r.lecture_title, *r.node_path]) if r.lecture_id else "Course"
        deck.add_note(genanki.Note(
            model=model,
            fields=[html.escape(r.item.front).replace("\n", "<br>"), html.escape(r.item.back).replace("\n", "<br>"), html.escape(topic)],
            guid=genanki.guid_for(r.item.id),
            tags=["nodebook", r.item.type],
        ))
    with tempfile.TemporaryDirectory(prefix="nodebook-anki-") as tmp:
        out = Path(tmp) / "deck.apkg"
        genanki.Package(deck).write_to_file(str(out))
        return out.read_bytes()
