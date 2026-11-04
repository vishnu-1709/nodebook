"""Test me (SPEC §5.6) and answer grading (shared with Generate, §5.8)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from backend.core.ids import new_id
from backend.core.schemas import MapDoc, SlideRef
from backend.core.storage import Storage
from backend.llm.base import ChatMessage, LLMError, LLMProvider
from backend.llm.prompts import PromptLibrary
from backend.pipeline.context import SlideText, format_slide_texts, node_path, refs_for_numbers, slide_texts

Verdict = Literal["correct", "partly", "wrong"]
SCORE: dict[str, float] = {"correct": 1.0, "partly": 0.5, "wrong": 0.0}


class QOut(BaseModel):
    question: str
    slide: int


class QuestionsOut(BaseModel):
    questions: list[QOut]


class TestQuestion(BaseModel):
    id: str = Field(default_factory=new_id)
    question: str
    source: SlideRef | None = None


class GradeOut(BaseModel):
    verdict: Verdict
    feedback: str
    slide: int | None = None


class GradesOut(BaseModel):
    grades: list[GradeOut]


class GradeItem(BaseModel):
    question: str
    answer: str = ""
    reference: str = ""  # expected answer, when known (Generate)
    source: SlideRef | None = None


class GradeResult(BaseModel):
    question: str
    answer: str
    verdict: Verdict
    feedback: str
    source: SlideRef | None = None


def generate_questions(
    st: Storage, provider: LLMProvider, prompts: PromptLibrary, model: str,
    course_id: str, doc: MapDoc, node_id: str, count: int = 3,
) -> list[TestQuestion]:
    node = doc.nodes[node_id]
    if not node.sources:
        raise LLMError("This topic has no slides linked, so there's nothing to test from. Link a slide first.")
    p = prompts.get("test_me_generate")
    texts = slide_texts(st, course_id, node.sources)
    msgs = [
        ChatMessage(role="system", content=p.section("system", count=count)),
        ChatMessage(role="user", content=p.section("user", path=" › ".join(node_path(doc, node_id)),
                                                   slides=format_slide_texts(texts))),
    ]
    out = provider.structured(msgs, model, QuestionsOut, tag="test_me_generate")
    allowed = node.sources
    qs: list[TestQuestion] = []
    seen: set[str] = set()
    for q in out.questions:
        text = " ".join(q.question.split())
        if not text or text.lower() in seen:
            continue
        seen.add(text.lower())
        refs = refs_for_numbers([q.slide], allowed)
        # AC: questions reference only that node's slides — fall back to the node's first slide
        qs.append(TestQuestion(question=text, source=refs[0] if refs else allowed[0]))
        if len(qs) == count:
            break
    if not qs:
        raise LLMError("The model didn't return any usable questions. Try again.")
    return qs


def grade(
    st: Storage, provider: LLMProvider, prompts: PromptLibrary, model: str,
    course_id: str, items: list[GradeItem], context: list[SlideText] | None = None,
) -> list[GradeResult]:
    p = prompts.get("grade_answer")
    refs: list[SlideRef] = []
    for it in items:
        if it.source and it.source not in refs:
            refs.append(it.source)
    texts = context if context is not None else slide_texts(st, course_id, refs)
    rows = []
    for i, it in enumerate(items, 1):
        row = f"{i}. Question: {it.question}\n   Student answer: {it.answer.strip() or '(blank)'}"
        if it.reference:
            row += f"\n   Reference answer: {it.reference}"
        rows.append(row)
    msgs = [
        ChatMessage(role="system", content=p.section("system")),
        ChatMessage(role="user", content=p.section("user", slides=format_slide_texts(texts), items="\n".join(rows))),
    ]
    out = provider.structured(msgs, model, GradesOut, tag="grade_answer")
    results: list[GradeResult] = []
    for i, it in enumerate(items):
        g = out.grades[i] if i < len(out.grades) else GradeOut(verdict="wrong", feedback="Couldn't grade this one.")
        verdict: Verdict = "wrong" if not it.answer.strip() else g.verdict
        src = it.source
        if g.slide is not None:
            matched = refs_for_numbers([g.slide], refs)
            src = matched[0] if matched else src
        results.append(GradeResult(question=it.question, answer=it.answer, verdict=verdict,
                                   feedback=" ".join(g.feedback.split())[:300], source=src))
    return results


def score_of(results: list[GradeResult]) -> float:
    return sum(SCORE[r.verdict] for r in results) / max(len(results), 1)
