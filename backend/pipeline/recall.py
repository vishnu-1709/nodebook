"""Recall tests (SPEC §5.13): blank-map recall and explain-it-back."""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from pydantic import BaseModel, Field

from backend.core.schemas import MapDoc, SlideRef
from backend.core.storage import Storage
from backend.llm.base import ChatMessage, LLMError, LLMProvider
from backend.llm.prompts import PromptLibrary
from backend.pipeline.context import format_slide_texts, node_path, refs_for_numbers, slide_texts

EXACT = 0.86  # similarity at/above this is a match without asking the model


def norm(s: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9α-ωλ²³ ]+", " ", s.lower()).split())


def similarity(a: str, b: str) -> float:
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    seq = SequenceMatcher(None, a, b).ratio()
    ta, tb = set(a.split()), set(b.split())
    jac = len(ta & tb) / len(ta | tb) if ta | tb else 0.0
    return max(seq, jac)


class RecallAnswer(BaseModel):
    node_id: str
    typed: str = ""


class NodeVerdict(BaseModel):
    node_id: str
    expected: str
    typed: str
    correct: bool
    how: str  # exact | fuzzy | judged | blank | wrong


class JudgeItem(BaseModel):
    same: bool


class JudgeOut(BaseModel):
    verdicts: list[JudgeItem]


def judge_recall(
    provider: LLMProvider, prompts: PromptLibrary, model: str, doc: MapDoc, lecture_title: str,
    answers: list[RecallAnswer],
) -> list[NodeVerdict]:
    out: list[NodeVerdict] = []
    ask: list[int] = []
    for a in answers:
        node = doc.nodes.get(a.node_id)
        if node is None or a.node_id == doc.root_id:
            continue
        typed = a.typed.strip()
        if not typed:
            out.append(NodeVerdict(node_id=a.node_id, expected=node.label, typed="", correct=False, how="blank"))
            continue
        sim = similarity(node.label, typed)
        if sim >= EXACT:
            out.append(NodeVerdict(node_id=a.node_id, expected=node.label, typed=typed, correct=True,
                                   how="exact" if sim == 1.0 else "fuzzy"))
        else:
            # near-misses and synonyms (which can look nothing alike): the model decides
            out.append(NodeVerdict(node_id=a.node_id, expected=node.label, typed=typed, correct=False, how="wrong"))
            ask.append(len(out) - 1)
    if ask:
        p = prompts.get("recall_judge")
        rows = "\n".join(f"{k + 1}. expected: {out[i].expected!r} · typed: {out[i].typed!r}" for k, i in enumerate(ask))
        try:
            res = provider.structured(
                [ChatMessage(role="system", content=p.section("system")),
                 ChatMessage(role="user", content=p.section("user", lecture=lecture_title, items=rows))],
                model, JudgeOut, tag="recall_judge",
            )
            for k, i in enumerate(ask):
                if k < len(res.verdicts) and res.verdicts[k].same:
                    out[i].correct = True
                    out[i].how = "judged"
        except LLMError:
            pass  # fuzzy results stand; the UI still shows them
    return out


class Point(BaseModel):
    point: str
    slide: int = 0
    correction: str = ""


class ExplainOut(BaseModel):
    covered: list[str] = Field(default_factory=list)
    missing: list[Point] = Field(default_factory=list)
    wrong: list[Point] = Field(default_factory=list)
    score: float = 0.0


class CitedPoint(BaseModel):
    point: str
    correction: str = ""
    source: SlideRef | None = None


class ExplainReview(BaseModel):
    covered: list[str]
    missing: list[CitedPoint]
    wrong: list[CitedPoint]
    score: float


def review_explanation(
    st: Storage, provider: LLMProvider, prompts: PromptLibrary, model: str, course_id: str, doc: MapDoc,
    node_id: str, text: str,
) -> ExplainReview:
    node = doc.nodes[node_id]
    if not node.sources:
        raise LLMError("This topic has no slides linked, so there's nothing to check your explanation against.")
    p = prompts.get("explain_back_review")
    msg = p.section("user", path=" › ".join(node_path(doc, node_id)),
                    slides=format_slide_texts(slide_texts(st, course_id, node.sources)), text=text)
    out = provider.structured([ChatMessage(role="system", content=p.section("system")),
                               ChatMessage(role="user", content=msg)], model, ExplainOut, tag="explain_back_review")

    def cite(pts: list[Point]) -> list[CitedPoint]:
        res = []
        for x in pts:
            refs = refs_for_numbers([x.slide], node.sources)
            res.append(CitedPoint(point=x.point.strip(), correction=x.correction.strip(), source=refs[0] if refs else None))
        return [c for c in res if c.point]

    return ExplainReview(covered=[c.strip() for c in out.covered if c.strip()], missing=cite(out.missing),
                         wrong=cite(out.wrong), score=max(0.0, min(1.0, out.score)))
