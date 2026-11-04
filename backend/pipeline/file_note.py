"""AI suggestion of where an inbox note belongs (SPEC §5.7)."""

from __future__ import annotations

from pydantic import BaseModel

from backend.core.courses import list_courses, list_lectures
from backend.core.schemas import MapDoc, NoteDestination
from backend.core.storage import Storage
from backend.llm.base import ChatMessage, LLMProvider
from backend.llm.prompts import PromptLibrary

MAX_OPTIONS = 250


class FileOut(BaseModel):
    option: int


def destinations(st: Storage) -> list[NoteDestination]:
    out: list[NoteDestination] = []
    for c in list_courses(st):
        out.append(NoteDestination(course_id=c.id, label=c.name))
        for lec in list_lectures(st, c.id):
            out.append(NoteDestination(course_id=c.id, lecture_id=lec.id, label=f"{c.name} › {lec.title}"))
            path = st.paths.map(c.id, lec.id)
            if not st.exists(path):
                continue
            doc = st.read_doc(path, MapDoc)

            def walk(nid: str, trail: list[str], depth: int) -> None:
                n = doc.nodes[nid]
                if depth > 0:
                    out.append(NoteDestination(course_id=c.id, lecture_id=lec.id, node_id=nid,
                                               label=" › ".join([c.name, lec.title, *trail, n.label])))
                if depth < 3:
                    for ch in n.children:
                        if ch in doc.nodes:
                            walk(ch, trail + ([n.label] if depth > 0 else []), depth + 1)

            walk(doc.root_id, [], 0)
    return out[:MAX_OPTIONS]


def suggest_destination(
    st: Storage, provider: LLMProvider, prompts: PromptLibrary, model: str, text: str
) -> NoteDestination | None:
    options = destinations(st)
    if not options:
        return None
    p = prompts.get("file_note")
    listing = "\n".join(f"{i}. {d.label}" for i, d in enumerate(options, 1))
    msgs = [ChatMessage(role="system", content=p.section("system")),
            ChatMessage(role="user", content=p.section("user", note=text, options=listing))]
    out = provider.structured(msgs, model, FileOut, tag="file_note")
    if 1 <= out.option <= len(options):
        return options[out.option - 1]
    return None
