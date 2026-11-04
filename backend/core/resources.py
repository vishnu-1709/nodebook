"""Locate bundled read-only resources (static app, prompts, config) both in a
source checkout and inside a PyInstaller build (sys._MEIPASS)."""

from __future__ import annotations

import sys
from pathlib import Path


def resource_root() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    if base:
        return Path(base)
    return Path(__file__).resolve().parent.parent.parent


def static_dir() -> Path:
    return resource_root() / "backend" / "static"


def prompts_dir() -> Path:
    return resource_root() / "backend" / "prompts"


def config_dir() -> Path:
    return resource_root() / "config"
