"""Prompt templates live in backend/prompts/*.md (SPEC §7).

File format::

    <!-- prompt: map_chunk · version: 1 -->
    ## system
    ...text...
    ## user
    ...text with {{placeholders}}...

Optional extra sections (``## mode: hint`` etc.) are exposed via ``Prompt.section``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

_HEADER = re.compile(r"<!--\s*prompt:\s*(?P<name>[\w-]+)\s*·\s*version:\s*(?P<ver>\d+)\s*-->")
_SECTION = re.compile(r"^##\s+(?P<name>[\w: -]+?)\s*$", re.MULTILINE)
_VAR = re.compile(r"\{\{\s*(\w+)\s*\}\}")


class PromptError(KeyError):
    pass


@dataclass
class Prompt:
    name: str
    version: int
    sections: dict[str, str] = field(default_factory=dict)

    def section(self, name: str, **vars: object) -> str:
        if name not in self.sections:
            raise PromptError(f"prompt {self.name!r} has no section {name!r}")
        return render(self.sections[name], **vars)

    def has(self, name: str) -> bool:
        return name in self.sections


def render(template: str, **vars: object) -> str:
    def sub(m: re.Match[str]) -> str:
        key = m.group(1)
        if key not in vars:
            raise PromptError(f"missing prompt variable {key!r}")
        return str(vars[key])

    return _VAR.sub(sub, template).strip()


def parse_prompt(text: str, fallback_name: str = "") -> Prompt:
    m = _HEADER.search(text)
    name = m.group("name") if m else fallback_name
    version = int(m.group("ver")) if m else 0
    body = text[m.end():] if m else text
    parts = _SECTION.split(body)
    sections: dict[str, str] = {}
    # parts = [preamble, name1, body1, name2, body2, ...]
    for i in range(1, len(parts) - 1, 2):
        sections[parts[i].strip().lower()] = parts[i + 1].strip()
    return Prompt(name=name, version=version, sections=sections)


class PromptLibrary:
    def __init__(self, directory: Path = PROMPTS_DIR) -> None:
        self.dir = directory
        self.prompts: dict[str, Prompt] = {}
        self.reload()

    def reload(self) -> None:
        self.prompts = {}
        for f in sorted(self.dir.glob("*.md")):
            p = parse_prompt(f.read_text("utf-8"), fallback_name=f.stem)
            self.prompts[p.name] = p

    def get(self, name: str) -> Prompt:
        try:
            return self.prompts[name]
        except KeyError as exc:
            raise PromptError(f"prompt {name!r} not found in {self.dir}") from exc
