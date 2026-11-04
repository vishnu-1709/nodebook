"""AppContext: the single holder of process state (settings, storage, jobs,
provider). Created once by ``create_app`` and stored on ``app.state``."""

from __future__ import annotations

import os
import threading
from pathlib import Path

import backend.core.migrations  # noqa: F401  (registers migrations)
from backend.core.jobs import JobManager
from backend.core.settings import Settings, SettingsPatch, SettingsStore
from backend.core.storage import Storage
from backend.llm.base import LLMProvider
from backend.llm.factory import make_provider
from backend.llm.prompts import PromptLibrary


class AppContext:
    def __init__(
        self,
        settings_store: SettingsStore,
        provider: LLMProvider | None = None,
        jobs: JobManager | None = None,
    ) -> None:
        self.settings_store = settings_store
        self._lock = threading.RLock()
        self.settings: Settings = settings_store.load()
        if os.environ.get("NODEBOOK_FAKE_LLM") == "1" and provider is None:
            self.settings.provider = "fake"
        self._fixed_provider = provider
        self.provider: LLMProvider = provider or make_provider(self.settings)
        self.storage = Storage(self.settings.data_dir)
        self.jobs = jobs or JobManager()
        self.prompts = PromptLibrary()

    def update_settings(self, patch: SettingsPatch) -> Settings:
        with self._lock:
            provider_kind = self.settings.provider
            new = self.settings_store.update(patch)
            new.provider = provider_kind
            old_dir, old_url = self.settings.data_dir, self.settings.ollama_url
            self.settings = new
            if new.data_dir != old_dir:
                self.storage = Storage(new.data_dir)
            if new.ollama_url != old_url and self._fixed_provider is None:
                self.provider = make_provider(new)
            return new

    def require_model(self, slot: str) -> str:
        """Model name for 'map' or 'study', or a plain error telling the user what to do."""
        from backend.llm.base import LLMError

        name = self.settings.map_model if slot == "map" else self.settings.study_model
        if not name:
            other = self.settings.study_model if slot == "map" else self.settings.map_model
            if other:
                return other
            raise LLMError("No model chosen yet. Pick one in Settings → Ollama.")
        return name

    @property
    def data_dir(self) -> Path:
        return self.storage.paths.root
