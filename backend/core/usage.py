"""Local feature-use log (SPEC §5.16): feature name + timestamp only. Never
shown in the UI, never sent anywhere."""

from __future__ import annotations

from backend.core.context import AppContext
from backend.core.schemas import UsageEvent


def log_usage(ctx: AppContext, feature: str) -> None:
    if not ctx.settings.usage_log:
        return
    try:
        ctx.storage.append_jsonl(ctx.storage.paths.usage, UsageEvent(feature=feature))
    except OSError:
        pass  # never let the usage log break a feature
