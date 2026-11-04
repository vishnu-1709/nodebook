"""Pomodoro end-of-session "Quick brain check" (SPEC §5.11 v0.2)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.api.deps import get_ctx
from backend.core import maps as map_svc
from backend.core.context import AppContext
from backend.core.courses import NotFound, list_courses
from backend.core.schemas import SlideRef
from backend.core.usage import log_usage
from backend.llm.base import LLMError
from backend.pipeline.testme import generate_questions

router = APIRouter(tags=["pomodoro"])
QUESTIONS = 3


class Touched(BaseModel):
    course_id: str
    lecture_id: str
    node_id: str


class BrainIn(BaseModel):
    nodes: list[Touched] = Field(default_factory=list, max_length=50)
    started_at: str
    ended_at: str
    work_min: int = Field(ge=1, le=600)


class BrainQuestion(BaseModel):
    course_id: str
    lecture_id: str
    node_id: str
    node_label: str
    question: str
    source: SlideRef | None = None


class BrainOut(BaseModel):
    summary: str
    minutes: int
    nodes: int
    cards: int
    questions: list[BrainQuestion]


class _Row(BaseModel):
    reviewed_at: str


def _in(window: tuple[datetime, datetime], iso: str) -> bool:
    try:
        t = datetime.fromisoformat(iso)
    except ValueError:
        return False
    if t.tzinfo is None:
        t = t.replace(tzinfo=window[0].tzinfo)
    return window[0] <= t <= window[1]


@router.post("/brain-check")
def brain_check(body: BrainIn, ctx: AppContext = Depends(get_ctx)) -> BrainOut:
    st = ctx.storage
    start, end = datetime.fromisoformat(body.started_at), datetime.fromisoformat(body.ended_at)
    window = (start, end)
    cards = sum(1 for c in list_courses(st) for r in st.read_jsonl(st.paths.review_log(c.id), _Row) if _in(window, r.reviewed_at))
    seen: list[Touched] = []
    for n in body.nodes:
        if all(x.node_id != n.node_id for x in seen):
            seen.append(n)
    questions: list[BrainQuestion] = []
    if seen:
        model = ctx.require_model("study")
        per = [QUESTIONS // len(seen) + (1 if i < QUESTIONS % len(seen) else 0) for i in range(len(seen))][:QUESTIONS]
        for t, k in zip(seen, per):
            if k == 0:
                continue
            try:
                doc = map_svc.load_map(st, t.course_id, t.lecture_id)
                if t.node_id not in doc.nodes:
                    continue
                for q in generate_questions(st, ctx.provider, ctx.prompts, model, t.course_id, doc, t.node_id, count=k):
                    questions.append(BrainQuestion(course_id=t.course_id, lecture_id=t.lecture_id, node_id=t.node_id,
                                                   node_label=doc.nodes[t.node_id].label, question=q.question, source=q.source))
            except (LLMError, NotFound):
                continue  # a node without slides just contributes no question
    log_usage(ctx, "pomodoro.brain_check")
    n = len(seen)
    summary = f"{body.work_min} min · {n} node{'s' if n != 1 else ''} · {cards} card{'s' if cards != 1 else ''}"
    return BrainOut(summary=summary, minutes=body.work_min, nodes=n, cards=cards, questions=questions[:QUESTIONS])
