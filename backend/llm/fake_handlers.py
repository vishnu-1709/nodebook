"""Default canned behaviour for FakeProvider, so the app is usable offline.
Extended as features land (map_chunk, map_merge, node_answer, ...)."""

from __future__ import annotations

from typing import Any

from backend.llm.base import ChatMessage


def _echo(messages: list[ChatMessage], schema: Any = None) -> str:
    last = next((m.content for m in reversed(messages) if m.role == "user"), "")
    return f"(fake model) You said: {last[:200]}"


def default_handlers() -> dict[str, Any]:
    return {"*": _echo}
