"""Deterministic provider for tests and offline development.

Handlers are registered per ``tag`` (prompt name). A handler receives the
messages (and the schema for structured calls) and returns a str (chat) or a
dict / model instance (structured). Unregistered tags fall back to
``default_handlers`` (see ``backend/llm/fake_handlers.py``)."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

from pydantic import BaseModel

from backend.llm.base import (
    ChatMessage,
    LLMError,
    LLMProvider,
    M,
    ModelInfo,
    ProviderStatus,
    PullProgress,
    StructuredOutputError,
)

Handler = Callable[..., Any]


class FakeProvider(LLMProvider):
    def __init__(
        self,
        handlers: dict[str, Handler] | None = None,
        models: list[ModelInfo] | None = None,
        use_defaults: bool = True,
    ) -> None:
        super().__init__()
        self.handlers: dict[str, Handler] = {}
        if use_defaults:
            from backend.llm.fake_handlers import default_handlers

            self.handlers.update(default_handlers())
        self.handlers.update(handlers or {})
        self.models = models if models is not None else [
            ModelInfo(name="fake-map:latest", parameter_size="7B", family="fake"),
            ModelInfo(name="fake-study:latest", parameter_size="3B", family="fake"),
            ModelInfo(name="fake-vision:latest", parameter_size="7B", family="fake", vision=True),
        ]
        self.calls: list[dict[str, Any]] = []
        self.pulled: list[str] = []

    def status(self) -> ProviderStatus:
        return ProviderStatus(reachable=True, version="fake", url="fake://")

    def list_models(self) -> list[ModelInfo]:
        return list(self.models)

    def _handler(self, tag: str) -> Handler:
        h = self.handlers.get(tag) or self.handlers.get("*")
        if h is None:
            raise LLMError(f"FakeProvider has no handler for {tag!r}")
        return h

    def chat(self, messages: list[ChatMessage], model: str, tag: str = "") -> str:
        self.calls.append({"kind": "chat", "tag": tag, "model": model, "messages": messages})
        out = self._handler(tag)(messages=messages, schema=None)
        return str(out)

    def chat_stream(self, messages: list[ChatMessage], model: str, tag: str = "") -> Iterator[str]:
        text = self.chat(messages, model, tag)
        self.calls[-1]["kind"] = "chat_stream"
        words = text.split(" ")
        for i, w in enumerate(words):
            yield w if i == len(words) - 1 else w + " "

    def structured(self, messages: list[ChatMessage], model: str, schema: type[M], tag: str = "") -> M:
        self.calls.append({"kind": "structured", "tag": tag, "model": model, "messages": messages})
        out = self._handler(tag)(messages=messages, schema=schema)
        try:
            if isinstance(out, BaseModel):
                out = out.model_dump(mode="json")
            result = schema.model_validate(out)
        except Exception as exc:  # noqa: BLE001
            self.note_json_failure(model)
            raise StructuredOutputError(f"JSON did not match the expected shape: {exc}", str(out)) from exc
        self.note_json_success(model)
        return result

    def pull(self, name: str, on_progress: Callable[[PullProgress], None]) -> None:
        for i in range(0, 101, 25):
            on_progress(PullProgress(status="downloading", completed=i, total=100))
        on_progress(PullProgress(status="success", completed=100, total=100))
        self.pulled.append(name)
        if not any(m.name == name for m in self.models):
            self.models.append(ModelInfo(name=name))
