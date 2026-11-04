"""App settings, stored in the OS config dir (not the data folder) so the data
folder can live inside a synced drive."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Literal

import platformdirs
from pydantic import BaseModel, ConfigDict, Field

Theme = Literal["system", "light", "dark"]


class PomodoroPreset(BaseModel):
    work_min: int = 25
    break_min: int = 5


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    schema_version: int = Field(default=1, alias="schema")
    data_dir: str = Field(default_factory=lambda: str(Path.home() / "Documents" / "Nodebook"))
    onboarded: bool = False
    theme: Theme = "system"
    ollama_url: str = "http://localhost:11434"
    provider: Literal["ollama", "openai_compat", "fake"] = "ollama"
    map_model: str | None = None
    study_model: str | None = None
    keep_all_questions: bool = False
    usage_log: bool = True
    pomodoro_presets: list[PomodoroPreset] = Field(
        default_factory=lambda: [PomodoroPreset(), PomodoroPreset(work_min=50, break_min=10)]
    )


class SettingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_dir: str | None = None
    onboarded: bool | None = None
    theme: Theme | None = None
    ollama_url: str | None = None
    map_model: str | None = None
    study_model: str | None = None
    keep_all_questions: bool | None = None
    usage_log: bool | None = None
    pomodoro_presets: list[PomodoroPreset] | None = None


def default_config_dir() -> Path:
    override = os.environ.get("NODEBOOK_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    return Path(platformdirs.user_config_dir("Nodebook", appauthor=False))


class SettingsStore:
    """Loads/saves settings.json in the config dir (atomic write)."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self.dir = (config_dir or default_config_dir()).expanduser().resolve()
        self.path = self.dir / "settings.json"
        self._lock = threading.Lock()

    def load(self) -> Settings:
        with self._lock:
            if not self.path.exists():
                return Settings()
            try:
                return Settings.model_validate(json.loads(self.path.read_text("utf-8")))
            except (ValueError, json.JSONDecodeError):
                return Settings()

    def save(self, settings: Settings) -> None:
        with self._lock:
            self.dir.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name("settings.json.tmp")
            tmp.write_text(
                json.dumps(settings.model_dump(mode="json", by_alias=True), indent=2), "utf-8"
            )
            os.replace(tmp, self.path)

    def update(self, patch: SettingsPatch) -> Settings:
        current = self.load()
        merged = current.model_copy(update=patch.model_dump(exclude_unset=True))
        merged = Settings.model_validate(merged.model_dump(by_alias=True))
        self.save(merged)
        return merged
