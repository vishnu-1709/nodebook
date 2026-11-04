"""Stub for an OpenAI-compatible endpoint (llama.cpp server, LM Studio, vLLM).
Kept behind the same interface for later; not wired into the UI in v0.1."""

from __future__ import annotations

from collections.abc import Callable, Iterator

from backend.llm.base import ChatMessage, LLMError, LLMProvider, M, ModelInfo, ProviderStatus, PullProgress


class OpenAICompatProvider(LLMProvider):
    def __init__(self, base_url: str, api_key: str = "") -> None:
        super().__init__()
        self.base_url = base_url
        self.api_key = api_key

    def _todo(self) -> LLMError:
        return LLMError("OpenAI-compatible endpoints are not supported yet.")

    def status(self) -> ProviderStatus:
        return ProviderStatus(reachable=False, url=self.base_url, error=str(self._todo()))

    def list_models(self) -> list[ModelInfo]:
        raise self._todo()

    def chat(self, messages: list[ChatMessage], model: str, tag: str = "") -> str:
        raise self._todo()

    def chat_stream(self, messages: list[ChatMessage], model: str, tag: str = "") -> Iterator[str]:
        raise self._todo()

    def structured(self, messages: list[ChatMessage], model: str, schema: type[M], tag: str = "") -> M:
        raise self._todo()

    def pull(self, name: str, on_progress: Callable[[PullProgress], None]) -> None:
        raise self._todo()
