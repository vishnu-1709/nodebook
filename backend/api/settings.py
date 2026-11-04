from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_ctx
from backend.core.context import AppContext
from backend.core.settings import Settings, SettingsPatch

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("")
def get_settings(ctx: AppContext = Depends(get_ctx)) -> Settings:
    return ctx.settings


@router.patch("")
def patch_settings(patch: SettingsPatch, ctx: AppContext = Depends(get_ctx)) -> Settings:
    if patch.data_dir is not None:
        from pathlib import Path

        p = Path(patch.data_dir).expanduser()
        if not p.is_absolute():
            raise HTTPException(400, "Data folder must be an absolute path.")
        try:
            p.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise HTTPException(400, f"Can't use that folder: {exc}") from exc
        patch.data_dir = str(p.resolve())
    return ctx.update_settings(patch)
