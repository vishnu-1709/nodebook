from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.api.deps import get_ctx
from backend.core import maps as map_svc
from backend.core.context import AppContext
from backend.core.courses import get_lecture
from backend.core.ids import new_id
from backend.core.schemas import ResultRecord
from backend.core.status import recompute
from backend.core.usage import log_usage
from backend.pipeline.recall import ExplainReview, NodeVerdict, RecallAnswer, judge_recall, review_explanation

router = APIRouter(prefix="/courses/{course_id}/lectures/{lecture_id}", tags=["recall"])


class RecallIn(BaseModel):
    answers: list[RecallAnswer] = Field(min_length=1, max_length=500)


class RecallOut(BaseModel):
    session_id: str
    verdicts: list[NodeVerdict]
    correct: int
    total: int
    score: float


class ExplainIn(BaseModel):
    text: str = Field(min_length=1, max_length=10000)


class ExplainOut(BaseModel):
    review: ExplainReview
    record: ResultRecord


@router.post("/recall/judge")
def recall(course_id: str, lecture_id: str, body: RecallIn, ctx: AppContext = Depends(get_ctx)) -> RecallOut:
    st = ctx.storage
    lec = get_lecture(st, course_id, lecture_id)
    doc = map_svc.load_map(st, course_id, lecture_id)
    verdicts = judge_recall(ctx.provider, ctx.prompts, ctx.require_model("study"), doc, lec.title, body.answers)
    session = new_id()
    for v in verdicts:  # score per node (SPEC §5.13)
        st.append_jsonl(st.paths.results(course_id, lecture_id), ResultRecord(
            node_id=v.node_id, kind="recall", score=1.0 if v.correct else 0.0,
            details={"session_id": session, "typed": v.typed, "how": v.how}))
    recompute(st, course_id, lecture_id, [v.node_id for v in verdicts])
    correct = sum(v.correct for v in verdicts)
    log_usage(ctx, "recall.blank_map")
    return RecallOut(session_id=session, verdicts=verdicts, correct=correct, total=len(verdicts),
                     score=correct / max(1, len(verdicts)))


@router.post("/nodes/{node_id}/explain-back")
def explain_back(course_id: str, lecture_id: str, node_id: str, body: ExplainIn, ctx: AppContext = Depends(get_ctx)) -> ExplainOut:
    st = ctx.storage
    doc = map_svc.load_map(st, course_id, lecture_id)
    if node_id not in doc.nodes:
        raise HTTPException(404, "node not found")
    review = review_explanation(st, ctx.provider, ctx.prompts, ctx.require_model("study"), course_id, doc, node_id, body.text)
    rec = ResultRecord(node_id=node_id, kind="explain", score=review.score,
                       details={"text": body.text, **review.model_dump(mode="json")})
    st.append_jsonl(st.paths.results(course_id, lecture_id), rec)
    map_svc.patch_node(st, course_id, lecture_id, node_id, studied=True)
    recompute(st, course_id, lecture_id, [node_id])
    log_usage(ctx, "recall.explain_back")
    return ExplainOut(review=review, record=rec)
