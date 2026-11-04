from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.api.deps import get_ctx
from backend.core.context import AppContext
from backend.llm.base import LLMError, ModelInfo, ProviderStatus

router = APIRouter(prefix="/ollama", tags=["ollama"])


class StatusOut(BaseModel):
    status: ProviderStatus
    models: list[ModelInfo]
    models_error: str = ""
    json_warnings: list[str] = []


@router.get("/status")
def status(ctx: AppContext = Depends(get_ctx)) -> StatusOut:
    st = ctx.provider.status()
    models: list[ModelInfo] = []
    err = ""
    if st.reachable:
        try:
            models = ctx.provider.list_models()
        except LLMError as exc:
            err = str(exc)
    warnings = [m for m, n in ctx.provider.json_failures.items() if n >= 3]
    return StatusOut(status=st, models=models, models_error=err, json_warnings=warnings)
