from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.deps import get_ctx
from backend.core.clock import now_iso
from backend.core.context import AppContext
from backend.core.courses import get_course, get_lecture
from backend.core.notes import add_note
from backend.core.schemas import (
    Exchange,
    MapDoc,
    Message,
    NoteDestination,
    PracticeDoc,
    PracticeItem,
    PracticeOrigin,
    SlideRef,
    ThreadsDoc,
)
from backend.core.usage import log_usage
from backend.pipeline.generate import GeneratedItem, GenRequest, course_nodes, generate_one, suggest_node
from backend.pipeline.testme import GradeItem, GradeResult, grade

router = APIRouter(prefix="/courses/{course_id}/generate", tags=["generate"])


class CheckIn(BaseModel):
    question: str
    reference: str = ""
    answer: str
    sources: list[SlideRef] = []


class SaveIn(BaseModel):
    item: GeneratedItem
    destination: NoteDestination


class SavedOut(BaseModel):
    kind: str  # practice | note | exchange
    lecture_id: str | None
    node_id: str | None
    id: str


@router.post("")
def generate(course_id: str, req: GenRequest, ctx: AppContext = Depends(get_ctx)) -> GeneratedItem:
    get_course(ctx.storage, course_id)
    if req.type == "explain" and not req.topic.strip():
        raise HTTPException(400, "Type the topic you want explained.")
    if not req.source_ids and not req.lecture_ids:
        raise HTTPException(400, "Pick at least one source or lecture to generate from.")
    log_usage(ctx, f"generate.{req.type}")
    model = ctx.require_model("study")
    item = generate_one(ctx.storage, ctx.provider, ctx.prompts, model, course_id, req)
    item.suggested = suggest_node(ctx.storage, ctx.provider, ctx.prompts, model, course_id, item, req.lecture_ids)
    return item


@router.get("/destinations")
def destinations(course_id: str, ctx: AppContext = Depends(get_ctx)) -> list[NoteDestination]:
    get_course(ctx.storage, course_id)
    return [NoteDestination(course_id=course_id, label="Course (unassigned)"), *course_nodes(ctx.storage, course_id)]


@router.post("/check")
def check(course_id: str, body: CheckIn, ctx: AppContext = Depends(get_ctx)) -> GradeResult:
    log_usage(ctx, "generate.check")
    item = GradeItem(question=body.question, answer=body.answer, reference=body.reference,
                     source=body.sources[0] if body.sources else None)
    from backend.pipeline.context import slide_texts

    texts = slide_texts(ctx.storage, course_id, body.sources)
    return grade(ctx.storage, ctx.provider, ctx.prompts, ctx.require_model("study"), course_id, [item], texts)[0]


@router.post("/save", status_code=201)
def save(course_id: str, body: SaveIn, ctx: AppContext = Depends(get_ctx)) -> SavedOut:
    st = ctx.storage
    get_course(st, course_id)
    it, dest = body.item, body.destination
    lecture_id = dest.lecture_id
    node_id = dest.node_id if lecture_id else None
    if lecture_id:
        get_lecture(st, course_id, lecture_id)
        if node_id:
            doc = st.read_doc(st.paths.map(course_id, lecture_id), MapDoc)
            if node_id not in doc.nodes:
                raise HTTPException(400, "That topic no longer exists. Pick another.")
    origin = PracticeOrigin(kind="generate", source_ids=it.source_ids, ref=it.ref)
    log_usage(ctx, f"generate.save.{it.type}")

    if it.type in ("questions", "flashcards"):
        p = PracticeItem(
            type="question" if it.type == "questions" else "card",
            node_id=node_id, front=it.front, back=it.back, origin=origin,
            answer_status="ai_unverified",
        )
        path = st.paths.practice(course_id, lecture_id) if lecture_id else st.paths.course_practice(course_id)
        with st.update_doc(path, PracticeDoc, PracticeDoc) as doc:
            doc.items.append(p)
        return SavedOut(kind="practice", lecture_id=lecture_id, node_id=node_id, id=p.id)

    text = f"{it.title}\n\n{it.body}".strip()
    if it.ref:
        text += f"\n\n({it.ref})"
    if it.type == "explain" and lecture_id and node_id:
        ex = Exchange(kept_at=now_iso(), messages=[
            Message(role="user", kind="question", content=f"Explain: {it.title or 'this topic'}"),
            Message(role="assistant", kind="answer", content=it.body),
        ])
        with st.update_doc(st.paths.threads(course_id, lecture_id), ThreadsDoc, ThreadsDoc) as th:
            th.by_node.setdefault(node_id, []).append(ex)
        return SavedOut(kind="exchange", lecture_id=lecture_id, node_id=node_id, id=ex.id)
    note = add_note(st, course_id, lecture_id, text, node_id)
    return SavedOut(kind="note", lecture_id=lecture_id, node_id=node_id, id=note.id)
