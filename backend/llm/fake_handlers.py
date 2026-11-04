"""Default canned behaviour for FakeProvider, so the app is usable offline and
in tests. Each handler mimics what a decent model would return, using simple
text heuristics over the prompt."""

from __future__ import annotations

import re
from typing import Any

from backend.llm.base import ChatMessage

_SLIDE_RE = re.compile(r"\[Slide (\d+)\]\n(.*?)(?=\n\n\[Slide \d+\]|\Z)", re.S)
_SKIP = re.compile(r"^(outline|agenda|contents|questions\??|thank you|thanks|summary)\b", re.I)
_LINE_RE = re.compile(r"^(\s*)- (.+?) \(slides ([\d, ]+)\)$")


def _last_user(messages: list[ChatMessage]) -> str:
    for m in messages:
        if m.role == "user" and ("[Slide" in m.content or "Part 1" in m.content):
            return m.content
    return next((m.content for m in reversed(messages) if m.role == "user"), "")


def _echo(messages: list[ChatMessage], schema: Any = None) -> str:
    last = next((m.content for m in reversed(messages) if m.role == "user"), "")
    return f"(fake model) You said: {last[:200]}"


def _title(text: str) -> str:
    first = text.strip().splitlines()[0] if text.strip() else ""
    return " ".join(first.split()[:6])


def map_chunk(messages: list[ChatMessage], schema: Any = None) -> dict[str, Any]:
    text = _last_user(messages)
    slides = [(int(n), body.strip()) for n, body in _SLIDE_RE.findall(text)]
    useful = [(n, b) for n, b in slides if b and not b.startswith("(no text") and not _SKIP.match(_title(b))]
    if len(useful) <= 1 and len(slides) > 1:
        useful = [(n, b) for n, b in slides if b and not b.startswith("(no text")]
    topics = []
    for i in range(0, len(useful), 3):
        group = useful[i : i + 3]
        head_n, head_b = group[0]
        topics.append({
            "label": _title(head_b) or f"Slide {head_n}",
            "slides": [n for n, _ in group],
            "subtopics": [{"label": _title(b), "slides": [n]} for n, b in group[1:] if _title(b)],
        })
    return {"topics": topics}


def map_merge(messages: list[ChatMessage], schema: Any = None) -> dict[str, Any]:
    text = _last_user(messages)
    topics: list[dict[str, Any]] = []
    for line in text.splitlines():
        m = _LINE_RE.match(line)
        if not m:
            continue
        indent, label, nums = m.groups()
        slides = [int(x) for x in nums.replace(" ", "").split(",") if x]
        if not indent:
            topics.append({"label": label, "slides": slides, "children": []})
        elif topics:
            topics[-1]["children"].append({"label": label, "slides": slides, "children": []})
    # group into at most 6 top-level sections, like a model tidying the tree
    if len(topics) > 6:
        size = -(-len(topics) // 6)
        grouped = []
        for i in range(0, len(topics), size):
            part = topics[i : i + size]
            head = part[0]
            children = [{"label": t["label"], "slides": t["slides"],
                         "children": [{"label": c["label"], "slides": c["slides"]} for c in t["children"]]}
                        for t in part[1:]]
            grouped.append({"label": head["label"], "slides": head["slides"],
                            "children": [{"label": c["label"], "slides": c["slides"],
                                          "children": []} for c in head["children"]] + children})
        topics = grouped
    return {"topics": topics}


def default_handlers() -> dict[str, Any]:
    return {"*": _echo, "map_chunk": map_chunk, "map_merge": map_merge}
