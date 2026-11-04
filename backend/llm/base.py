"""Provider interface (SPEC §2). Every LLM call in the app goes through this."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterator
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, Field, ValidationError

M = TypeVar("M", bound=BaseModel)


class LLMError(RuntimeError):
    """A plain-language failure the UI can show next to a Retry button."""


class StructuredOutputError(LLMError):
    """The model returned something that does not match the requested schema."""

    def __init__(self, message: str, raw: str = "") -> None:
        super().__init__(message)
        self.raw = raw


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str
    images: list[str] = Field(default_factory=list)  # base64 PNGs (vision models)


class ModelInfo(BaseModel):
    name: str
    size_bytes: int = 0
    parameter_size: str = ""
    family: str = ""
    vision: bool = False


class ProviderStatus(BaseModel):
    reachable: bool
    version: str = ""
    url: str = ""
    error: str = ""


class PullProgress(BaseModel):
    status: str
    completed: int = 0
    total: int = 0


def schema_for(model: type[BaseModel]) -> dict[str, Any]:
    """JSON schema generated from the pydantic model (SPEC §7)."""
    return model.model_json_schema()


def parse_structured(model: type[M], raw: str) -> M:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:]
    try:
        return model.model_validate(json.loads(text))
    except json.JSONDecodeError as exc:
        raise StructuredOutputError(f"model did not return valid JSON: {exc}", raw) from exc
    except ValidationError as exc:
        raise StructuredOutputError(f"JSON did not match the expected shape: {exc}", raw) from exc


class LLMProvider(ABC):
    """``tag`` names the prompt (e.g. "map_chunk"); real providers ignore it,
    FakeProvider uses it to pick a canned response."""

    def __init__(self) -> None:
        self.json_failures: dict[str, int] = {}

    def note_json_failure(self, model: str) -> None:
        self.json_failures[model] = self.json_failures.get(model, 0) + 1

    def note_json_success(self, model: str) -> None:
        self.json_failures[model] = 0

    @abstractmethod
    def status(self) -> ProviderStatus: ...

    @abstractmethod
    def list_models(self) -> list[ModelInfo]: ...

    @abstractmethod
    def chat(self, messages: list[ChatMessage], model: str, tag: str = "") -> str: ...

    @abstractmethod
    def chat_stream(self, messages: list[ChatMessage], model: str, tag: str = "") -> Iterator[str]: ...

    @abstractmethod
    def structured(
        self, messages: list[ChatMessage], model: str, schema: type[M], tag: str = ""
    ) -> M: ...

    @abstractmethod
    def pull(self, name: str, on_progress: Callable[[PullProgress], None]) -> None: ...
