from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from backend.core.schemas import MapDoc, SlideRef
from backend.llm.fake import FakeProvider
from backend.llm.prompts import PromptLibrary
from backend.pipeline.map_builder import (
    MAX_CHILDREN,
    BuildInput,
    DeckSlide,
    Draft,
    MapBuilder,
    TreeError,
    clean_label,
    normalize,
    validate_drafts,
)
from backend.pipeline.parse_pdf import parse_pdf

DECKS = Path(__file__).resolve().parent.parent / "fixtures" / "decks"
SID = "01JAAAAAAAAAAAAAAAAAAAAAAA"


def deck() -> list[DeckSlide]:
    return [DeckSlide(SlideRef(source_id=SID, slide=s.number), s) for s in parse_pdf(DECKS / "linear_regression.pdf")]


def build(provider: FakeProvider, slides: list[DeckSlide] | None = None, **kw: Any):  # noqa: ANN201
    inp = BuildInput(lecture_id=SID, lecture_title="Linear Regression", slides=slides or deck(), model="m", **kw)
    return MapBuilder(provider, PromptLibrary()).build(inp)


def check_tree(doc: MapDoc, n_slides: int) -> None:
    root = doc.nodes[doc.root_id]
    labels = set()

    def walk(nid: str, depth: int) -> None:
        n = doc.nodes[nid]
        assert depth <= 3
        assert len(n.children) <= MAX_CHILDREN
        assert n.sources, n.label
        assert all(1 <= s.slide <= n_slides for s in n.sources)
        assert len(n.label.split()) <= 6
        if nid != doc.root_id:
            assert n.label.lower() not in labels
            labels.add(n.label.lower())
        for c in n.children:
            assert doc.nodes[c].parent_id == nid
            walk(c, depth + 1)

    walk(root.id, 0)
    assert len(doc.nodes) > 5


def test_full_pipeline_valid_tree_and_coverage() -> None:
    fake = FakeProvider()
    res = build(fake)
    check_tree(res.map, 25)
    assert not res.fallback
    # 25 slides / 12 per chunk → 3 chunk calls + 1 merge
    tags = [c["tag"] for c in fake.calls]
    assert tags == ["map_chunk", "map_chunk", "map_chunk", "map_merge"]
    uncovered = {r.slide for r in res.uncovered}
    assert 2 in uncovered  # "Outline" slide skipped by the model
    assert 5 not in uncovered


def test_prompts_say_answer_only_from_slides() -> None:
    lib = PromptLibrary()
    for name in ("map_chunk", "map_merge"):
        assert "only from the provided" in lib.get(name).section("system").lower()


def test_caps_enforced_in_code() -> None:
    wide = [Draft(f"Topic number {i}", {i}) for i in range(1, 16)]
    wide.append(Draft("deep", {1}, [Draft("d2", {2}, [Draft("d3", {3}, [Draft("d4", {4})])])]))
    wide.append(Draft("A very long label with far too many words in it", {5}))
    wide.append(Draft("topic NUMBER 3", {9}))  # duplicate after normalisation
    wide.append(Draft("No sources", set()))
    wide.append(Draft("Bad slide", {99}))
    roots = normalize(wide, 20)
    validate_drafts(roots, 20)
    assert len(roots) <= MAX_CHILDREN
    flat = []

    def walk(d: Draft, depth: int) -> None:
        flat.append(d.label)
        assert depth <= 3
        for c in d.children:
            walk(c, depth + 1)

    for r in roots:
        walk(r, 1)
    assert "No sources" not in flat and "Bad slide" not in flat
    assert "d4" not in flat
    assert clean_label("A very long label with far too many words in it") in flat
    assert len([x for x in flat if x.lower() == "topic number 3"]) == 1


def test_validate_rejects_empty() -> None:
    with pytest.raises(TreeError):
        normalize([Draft("x", set())], 5)


def test_merge_retry_then_success() -> None:
    calls = {"n": 0}

    def flaky_merge(messages, schema):  # noqa: ANN001, ANN202
        calls["n"] += 1
        if calls["n"] == 1:
            return {"wrong": "shape"}
        assert "rejected" in messages[-1].content
        return {"topics": [{"label": "Least squares", "slides": [8, 9], "children": []},
                           {"label": "Gradient descent", "slides": [12, 13], "children": []}]}

    res = build(FakeProvider({"map_merge": flaky_merge}))
    assert calls["n"] == 2 and not res.fallback
    labels = {n.label for n in res.map.nodes.values()}
    assert {"Least squares", "Gradient descent"} <= labels


def test_merge_fails_twice_falls_back_flat() -> None:
    res = build(FakeProvider({"map_merge": lambda messages, schema: {"topics": "nope"}}))
    assert res.fallback
    assert any("flat" in w for w in res.warnings)
    check_tree(res.map, 25)


def test_chunk_fails_twice_uses_range_node() -> None:
    def bad_chunk(messages, schema):  # noqa: ANN001, ANN202
        return "garbage"

    fake = FakeProvider({"map_chunk": bad_chunk})
    res = build(fake)
    labels = {n.label for n in res.map.nodes.values()}
    assert "Slides 1–12" in labels
    assert res.warnings


def test_vision_images_sent_for_figure_slides() -> None:
    fake = FakeProvider()
    res = build(fake, vision=True, image_for=lambda ref: b"PNG" if ref.slide == 23 else None)
    sent = [m for c in fake.calls if c["tag"] == "map_chunk" for m in c["messages"] if m.images]
    assert len(sent) == 1 and "slide 23" in sent[0].content
    assert res.map


def test_no_images_without_vision() -> None:
    fake = FakeProvider()
    build(fake, vision=False, image_for=lambda ref: b"PNG")
    assert not any(m.images for c in fake.calls for m in c["messages"])
