from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.api.deps import get_ctx
from backend.core.context import AppContext
from backend.core.courses import NotFound
from backend.core.schemas import PracticeDoc, PracticeItem

router = APIRouter(prefix="/courses/{course_id}/lectures/{lecture_id}/practice", tags=["practice"])


@router.get("")
def list_practice(course_id: str, lecture_id: str, node_id: str | None = None,
                  ctx: AppContext = Depends(get_ctx)) -> list[PracticeItem]:
    st = ctx.storage
    items = st.read_doc(st.paths.practice(course_id, lecture_id), PracticeDoc, PracticeDoc).items
    if node_id is not None:
        items = [i for i in items if i.node_id == node_id]
    return items


class PracticePatch(BaseModel):
    front: str | None = None
    back: str | None = None
    answer_status: Literal["ai_unverified", "verified"] | None = None


@router.patch("/{item_id}")
def patch_item(course_id: str, lecture_id: str, item_id: str, body: PracticePatch,
               ctx: AppContext = Depends(get_ctx)) -> PracticeItem:
    st = ctx.storage
    with st.update_doc(st.paths.practice(course_id, lecture_id), PracticeDoc, PracticeDoc) as doc:
        for it in doc.items:
            if it.id == item_id:
                for k, v in body.model_dump(exclude_none=True).items():
                    setattr(it, k, v)
                return it
    raise NotFound("practice item not found")
