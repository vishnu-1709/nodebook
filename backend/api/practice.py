from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.api.deps import get_ctx
from backend.core.context import AppContext
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
