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


def _slides_in(messages: list[ChatMessage]) -> list[tuple[int, str]]:
    text = next((m.content for m in reversed(messages) if m.role == "user"), "")
    return [(int(n), b.strip()) for n, b in _SLIDE_RE.findall(text)]


def _lines(slides: list[tuple[int, str]]) -> list[tuple[int, str]]:
    out = []
    for n, body in slides:
        for ln in body.splitlines()[1:]:
            ln = ln.strip("•-* ").strip()
            if ln:
                out.append((n, " ".join(ln.split()[:5])))
    return out


def node_expand(messages: list[ChatMessage], schema: Any = None) -> dict[str, Any]:
    lines = _lines(_slides_in(messages))[:4]
    return {"subtopics": [{"label": l, "slides": [n]} for n, l in lines]}


def node_split(messages: list[ChatMessage], schema: Any = None) -> dict[str, Any]:
    slides = _slides_in(messages)
    if len(slides) >= 2:
        half = len(slides) // 2
        a, b = slides[:half], slides[half:]
        return {"parts": [{"label": _title(a[0][1]) or "Part one", "slides": [n for n, _ in a]},
                          {"label": _title(b[0][1]) or "Part two", "slides": [n for n, _ in b]}]}
    lines = _lines(slides)[:2]
    return {"parts": [{"label": l, "slides": [n]} for n, l in lines]}


def node_merge(messages: list[ChatMessage], schema: Any = None) -> dict[str, Any]:
    text = next((m.content for m in reversed(messages) if m.role == "user"), "")
    m = re.search(r'"(.+?)" and "(.+?)"', text)
    a, b = (m.group(1), m.group(2)) if m else ("Topic", "topic")
    return {"label": f"{a.split()[0]} and {b.split()[0]}"}


def node_simplify(messages: list[ChatMessage], schema: Any = None) -> dict[str, Any]:
    text = next((m.content for m in reversed(messages) if m.role == "user"), "")
    m = re.search(r'label "(.+?)"', text)
    label = m.group(1) if m else "Topic"
    return {"label": " ".join(label.split()[:3])}


def node_answer(messages: list[ChatMessage], schema: Any = None) -> str:
    system = messages[0].content if messages else ""
    slides = [int(n) for n, _ in _SLIDE_RE.findall(system)]
    cite = f" (slide {slides[0]})" if slides else ""
    q = messages[-1].content if messages else ""
    if "Do NOT answer yet" in system:
        return f"Before I explain: what do you think? Have a look at the slides{cite} and tell me your first idea."
    if "Give only a nudge" in system or "give one more hint" in system:
        return f"Hint: think about what the slide{cite} says first."
    if "has tried to answer" in system:
        return f"Partly correct — you have the right idea.{cite} The full answer: the slides explain it step by step."
    if "*why*" in system:
        return f"Because the method minimises the error{cite}."
    if "worked example" in system:
        return f"Example: with two points the line passes through both{cite}."
    if not slides:
        return "The slides don't cover this."
    return f"Here is the answer from the slides{cite}: {q[:80]}"


def test_me_generate(messages: list[ChatMessage], schema: Any = None) -> dict[str, Any]:
    slides = _slides_in(messages)
    m = re.search(r"Exactly (\d+) questions", messages[0].content)
    count = int(m.group(1)) if m else 3
    qs = []
    for n, l in (_lines(slides) or [(n, _title(b)) for n, b in slides]):
        qs.append({"question": f"Explain: {l}?", "slide": n})
    while slides and len(qs) < count:
        n = slides[0][0]
        qs.append({"question": f"What is the key idea of slide {n} (variant {len(qs) + 1})?", "slide": n})
    return {"questions": qs[:count]}


def grade_answer(messages: list[ChatMessage], schema: Any = None) -> dict[str, Any]:
    text = messages[-1].content
    slides = [int(n) for n, _ in _SLIDE_RE.findall(text)]
    answers = re.findall(r"Student answer: (.*)", text)
    grades = []
    for a in answers:
        a = a.strip()
        words = len(a.split()) if a != "(blank)" else 0
        verdict = "correct" if words >= 4 else "partly" if words >= 2 else "wrong"
        grades.append({"verdict": verdict, "feedback": f"Compare with the slide (slide {slides[0] if slides else 1}).",
                       "slide": slides[0] if slides else None})
    return {"grades": grades}


def file_note(messages: list[ChatMessage], schema: Any = None) -> dict[str, Any]:
    text = messages[-1].content
    m = re.search(r'"""(.*?)"""', text, re.S)
    note_words = set(re.findall(r"[a-z]{4,}", (m.group(1) if m else "").lower()))
    best, best_score = 0, 0
    for num, label in re.findall(r"^(\d+)\. (.+)$", text, re.M):
        score = len(note_words & set(re.findall(r"[a-z]{4,}", label.lower())))
        if score > best_score or (score == best_score and score > 0 and len(label) > 0):
            best, best_score = int(num), score
    return {"option": best}


_SRC_RE = re.compile(r"\[Source (\d+) · page (\d+)\]\n(.*?)(?=\n\n\[Source|\n\n===|\Z)", re.S)


def _generate(kind: str) -> Any:
    def handler(messages: list[ChatMessage], schema: Any = None) -> dict[str, Any]:
        system, user = messages[0].content, messages[-1].content
        excluded = system.split("Do not repeat or rephrase any of these earlier items:")[-1].lower()
        pyq = "PAST PAPER" in user
        for src, page, body in _SRC_RE.findall(user):
            lines = [ln.strip("•-* ").strip() for ln in body.splitlines() if ln.strip()]
            for ln in lines[1:] or lines:
                front = f"Explain: {ln}" if kind == "questions" else f"What is meant by: {ln}?"
                title = lines[0] if lines else "Topic"
                key = (front if kind in ("questions", "flashcards") else f"{title} - {ln}").lower()
                if re.sub(r"[^a-z0-9]+", " ", key).strip() in re.sub(r"[^a-z0-9]+", " ", excluded):
                    continue
                cite = [{"source": int(src), "page": int(page)}]
                ref = f"PYQ style (source {src})" if pyq else ""
                if kind in ("questions", "flashcards"):
                    return {"front": front, "back": f"From the slides: {ln}", "title": "", "body": "", "cites": cite, "ref": ref}
                return {"front": "", "back": "", "title": title, "body": f"- {ln}", "cites": cite, "ref": ref}
        return {"front": "", "back": "", "title": "", "body": "", "cites": [], "ref": ""}

    return handler


def suggest_node(messages: list[ChatMessage], schema: Any = None) -> dict[str, Any]:
    return file_note(messages, schema)


def node_cards(messages: list[ChatMessage], schema: Any = None) -> dict[str, Any]:
    text = messages[-1].content
    m = re.search(r'Note:\n"""(.*?)"""', text, re.S)
    if m:
        note = m.group(1).strip()
        return {"cards": [{"front": f"What does this note say: {note[:60]}?", "back": note, "slide": 0}]}
    existing = text.split("existing cards:")[-1].split("\n")[0].lower()
    cards = []
    for n, line in _lines(_slides_in(messages)):
        front = f"Recall: {line}?"
        if front.lower() in existing:
            continue
        cards.append({"front": front, "back": line, "slide": n})
    return {"cards": cards[:3]}


_SYNONYMS = [{"ols", "least squares"}, {"sgd", "stochastic gradient descent"}, {"l2", "ridge regression"}, {"l1", "lasso regression"}]


def recall_judge(messages: list[ChatMessage], schema: Any = None) -> dict[str, Any]:
    pairs = re.findall(r"expected: '(.*?)' · typed: '(.*?)'", messages[-1].content)
    out = []
    for exp, typed in pairs:
        e, t = exp.lower(), typed.lower()
        same = any(e in g and t in g for g in _SYNONYMS) or (t and (t in e or e in t))
        out.append({"same": bool(same)})
    return {"verdicts": out}


def explain_back_review(messages: list[ChatMessage], schema: Any = None) -> dict[str, Any]:
    text = messages[-1].content
    m = re.search(r'explanation:\n"""(.*?)"""', text, re.S)
    said = set(re.findall(r"[a-z]{4,}", (m.group(1) if m else "").lower()))
    covered, missing = [], []
    slides_part = text.split("Student's explanation:")[0]
    for n, line in _lines([(int(k), b.strip()) for k, b in _SLIDE_RE.findall(slides_part)]):
        words = set(re.findall(r"[a-z]{4,}", line.lower()))
        (covered if words & said else missing).append((n, line))
    total = max(1, len(covered) + len(missing))
    return {"covered": [l for _, l in covered], "missing": [{"point": l, "slide": n} for n, l in missing],
            "wrong": [], "score": round(len(covered) / total, 2)}


def default_handlers() -> dict[str, Any]:
    return {
        "*": _echo,
        "map_chunk": map_chunk,
        "map_merge": map_merge,
        "node_expand": node_expand,
        "node_split": node_split,
        "node_merge": node_merge,
        "node_simplify": node_simplify,
        "node_answer": node_answer,
        "test_me_generate": test_me_generate,
        "grade_answer": grade_answer,
        "file_note": file_note,
        "suggest_node": suggest_node,
        "node_cards": node_cards,
        "recall_judge": recall_judge,
        "explain_back_review": explain_back_review,
        "generate_questions": _generate("questions"),
        "generate_flashcards": _generate("flashcards"),
        "generate_summary": _generate("summary"),
        "generate_explain": _generate("explain"),
    }
