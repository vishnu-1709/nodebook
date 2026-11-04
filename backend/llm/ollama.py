"""Ollama native API provider (https://github.com/ollama/ollama/blob/main/docs/api.md)."""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any

import httpx

from backend.llm.base import (
    ChatMessage,
    LLMError,
    LLMProvider,
    M,
    ModelInfo,
    ProviderStatus,
    PullProgress,
    StructuredOutputError,
    parse_structured,
    schema_for,
)

_VISION_FAMILIES = {"clip", "mllama", "llava"}


def _msg(m: ChatMessage) -> dict[str, Any]:
    d: dict[str, Any] = {"role": m.role, "content": m.content}
    if m.images:
        d["images"] = m.images
    return d


class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str = "http://localhost:11434", timeout: float = 600.0) -> None:
        super().__init__()
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._vision_cache: dict[str, bool] = {}

    def _client(self, timeout: float | None = None) -> httpx.Client:
        return httpx.Client(base_url=self.base_url, timeout=timeout or self.timeout)

    @staticmethod
    def _wrap(exc: Exception) -> LLMError:
        if isinstance(exc, httpx.ConnectError):
            return LLMError("Can't reach Ollama. Is it running?")
        if isinstance(exc, httpx.TimeoutException):
            return LLMError("Ollama took too long to answer.")
        if isinstance(exc, httpx.HTTPStatusError):
            body = exc.response.text[:300]
            if exc.response.status_code == 404:
                return LLMError(f"Model not found in Ollama. Pull it in Settings. ({body})")
            return LLMError(f"Ollama error {exc.response.status_code}: {body}")
        return LLMError(f"Ollama request failed: {exc}")

    # -- status / models -------------------------------------------------------
    def status(self) -> ProviderStatus:
        try:
            with self._client(timeout=3.0) as c:
                r = c.get("/api/version")
                r.raise_for_status()
                return ProviderStatus(reachable=True, version=r.json().get("version", ""), url=self.base_url)
        except Exception as exc:  # noqa: BLE001
            return ProviderStatus(reachable=False, url=self.base_url, error=str(self._wrap(exc)))

    def _is_vision(self, c: httpx.Client, name: str, families: list[str]) -> bool:
        if name in self._vision_cache:
            return self._vision_cache[name]
        vision = bool(set(families) & _VISION_FAMILIES)
        try:
            r = c.post("/api/show", json={"model": name})
            if r.status_code == 200:
                caps = r.json().get("capabilities") or []
                vision = vision or "vision" in caps
        except httpx.HTTPError:
            pass
        self._vision_cache[name] = vision
        return vision

    def list_models(self) -> list[ModelInfo]:
        try:
            with self._client(timeout=10.0) as c:
                r = c.get("/api/tags")
                r.raise_for_status()
                out = []
                for m in r.json().get("models", []):
                    details = m.get("details") or {}
                    families = details.get("families") or []
                    out.append(
                        ModelInfo(
                            name=m["name"],
                            size_bytes=int(m.get("size", 0)),
                            parameter_size=details.get("parameter_size", ""),
                            family=details.get("family", ""),
                            vision=self._is_vision(c, m["name"], families),
                        )
                    )
                return out
        except Exception as exc:  # noqa: BLE001
            raise self._wrap(exc) from exc

    # -- chat ------------------------------------------------------------------
    def chat(self, messages: list[ChatMessage], model: str, tag: str = "") -> str:
        payload = {"model": model, "messages": [_msg(m) for m in messages], "stream": False}
        try:
            with self._client() as c:
                r = c.post("/api/chat", json=payload)
                r.raise_for_status()
                return str(r.json().get("message", {}).get("content", ""))
        except Exception as exc:  # noqa: BLE001
            raise self._wrap(exc) from exc

    def chat_stream(self, messages: list[ChatMessage], model: str, tag: str = "") -> Iterator[str]:
        payload = {"model": model, "messages": [_msg(m) for m in messages], "stream": True}
        try:
            with self._client() as c, c.stream("POST", "/api/chat", json=payload) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("error"):
                        raise LLMError(f"Ollama error: {data['error']}")
                    chunk = data.get("message", {}).get("content", "")
                    if chunk:
                        yield chunk
                    if data.get("done"):
                        break
        except LLMError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise self._wrap(exc) from exc

    def structured(
        self, messages: list[ChatMessage], model: str, schema: type[M], tag: str = ""
    ) -> M:
        payload = {
            "model": model,
            "messages": [_msg(m) for m in messages],
            "stream": False,
            "format": schema_for(schema),
            "options": {"temperature": 0},
        }
        try:
            with self._client() as c:
                r = c.post("/api/chat", json=payload)
                r.raise_for_status()
                raw = str(r.json().get("message", {}).get("content", ""))
        except Exception as exc:  # noqa: BLE001
            raise self._wrap(exc) from exc
        try:
            result = parse_structured(schema, raw)
        except StructuredOutputError:
            self.note_json_failure(model)
            raise
        self.note_json_success(model)
        return result

    # -- pull ------------------------------------------------------------------
    def pull(self, name: str, on_progress: Callable[[PullProgress], None]) -> None:
        try:
            with self._client(timeout=None) as c, c.stream(
                "POST", "/api/pull", json={"model": name, "stream": True}, timeout=None
            ) as r:
                r.raise_for_status()
                for line in r.iter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    if data.get("error"):
                        raise LLMError(f"Pull failed: {data['error']}")
                    on_progress(
                        PullProgress(
                            status=data.get("status", ""),
                            completed=int(data.get("completed", 0) or 0),
                            total=int(data.get("total", 0) or 0),
                        )
                    )
        except LLMError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise self._wrap(exc) from exc
        self._vision_cache.pop(name, None)
