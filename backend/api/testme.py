from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.api.deps import get_ctx
from backend.core import maps as map_svc
from backend.core.context import AppContext
from backend.core.schemas import ResultRecord
from backend.core.usage import log_usage
from backend.pipeline.testme import GradeItem, GradeResult, TestQuestion, generate_questions, grade, score_of

router = APIRouter(prefix="/courses/{course_id}/lectures/{lecture_id}/nodes/{node_id}", tags=["test-me"])


class TestOut(BaseModel):
    questions: list[TestQuestion]


class AnswersIn(BaseModel):
    items: list[GradeItem] = Field(min_length=1, max_length=10)
    save: bool = True  # False while checking one question at a time; True on the last


@router.post("/test-me")
def start_test(course_id: str, lecture_id: str, node_id: str, ctx: AppContext = Depends(get_ctx)) -> TestOut:
    st = ctx.storage
    doc = map_svc.load_map(st, course_id, lecture_id)
    if node_id not in doc.nodes:
        raise HTTPException(404, "node not found")
    log_usage(ctx, "test_me.start")
    map_svc.patch_node(st, course_id, lecture_id, node_id, studied=True)
    qs = generate_questions(st, ctx.provider, ctx.prompts, ctx.require_model("study"), course_id, doc, node_id)
    return TestOut(questions=qs)


@router.post("/test-me/grade")
def grade_test(course_id: str, lecture_id: str, node_id: str, body: AnswersIn,
               ctx: AppContext = Depends(get_ctx)) -> ResultRecord:
    st = ctx.storage
    doc = map_svc.load_map(st, course_id, lecture_id)
    node = doc.nodes.get(node_id)
    if node is None:
        raise HTTPException(404, "node not found")
    allowed = {(s.source_id, s.slide) for s in node.sources}
    for it in body.items:
        if it.source and (it.source.source_id, it.source.slide) not in allowed:
            it.source = node.sources[0] if node.sources else None
    results = grade(st, ctx.provider, ctx.prompts, ctx.require_model("study"), course_id, body.items)
    rec = ResultRecord(node_id=node_id, kind="test_me", score=score_of(results),
                       details={"items": [r.model_dump(mode="json") for r in results]})
    if body.save:
        st.append_jsonl(st.paths.results(course_id, lecture_id), rec)
        log_usage(ctx, "test_me.grade")
    return rec


class ResultsIn(BaseModel):
    results: list[GradeResult] = Field(min_length=1, max_length=10)


@router.post("/test-me/save")
def save_test(course_id: str, lecture_id: str, node_id: str, body: ResultsIn,
              ctx: AppContext = Depends(get_ctx)) -> ResultRecord:
    """Store a finished one-question-at-a-time test (each answer was graded already)."""
    st = ctx.storage
    doc = map_svc.load_map(st, course_id, lecture_id)
    if node_id not in doc.nodes:
        raise HTTPException(404, "node not found")
    rec = ResultRecord(node_id=node_id, kind="test_me", score=score_of(body.results),
                       details={"items": [r.model_dump(mode="json") for r in body.results]})
    st.append_jsonl(st.paths.results(course_id, lecture_id), rec)
    log_usage(ctx, "test_me.grade")
    return rec


@router.get("/history")
def history(course_id: str, lecture_id: str, node_id: str, ctx: AppContext = Depends(get_ctx)) -> list[ResultRecord]:
    st = ctx.storage
    rows = [r for r in st.read_jsonl(st.paths.results(course_id, lecture_id), ResultRecord) if r.node_id == node_id]
    rows.sort(key=lambda r: r.created_at, reverse=True)
    return rows
