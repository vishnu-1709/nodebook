from __future__ import annotations

from fastapi import Request

from backend.core.context import AppContext


def get_ctx(request: Request) -> AppContext:
    ctx: AppContext = request.app.state.ctx
    return ctx
