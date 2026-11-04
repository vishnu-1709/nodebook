from __future__ import annotations

from backend.core.settings import Settings
from backend.llm.base import LLMProvider
from backend.llm.fake import FakeProvider
from backend.llm.ollama import OllamaProvider
from backend.llm.openai_compat import OpenAICompatProvider


def make_provider(settings: Settings) -> LLMProvider:
    if settings.provider == "fake":
        return FakeProvider()
    if settings.provider == "openai_compat":
        return OpenAICompatProvider(settings.ollama_url)
    return OllamaProvider(settings.ollama_url)
