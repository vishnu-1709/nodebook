"""Map editing that preserves node IDs, sources, threads and practice items
(SPEC §5.3). When nodes disappear (delete, merge), anything attached to them is
re-homed to the nearest surviving node — nothing is lost."""

from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, Field

from backend.core.clock import now_iso
from backend.core.courses import NotFound, get_lecture, update_lecture
from backend.core.ids import is_id, new_id
from backend.core.schemas import (
    MapDoc,
    Node,
    NotesDoc,
    PracticeDoc,
    RecentDoc,
    SlideRef,
    SlidesDoc,
    Status,
    ThreadsDoc,
)
from backend.core.storage import Storage


class MapEditError(ValueError):
    pass


class TreeIn(BaseModel):
    """Structure sent by the map editor: ids, labels, order, collapsed."""

    id: str
    label: str = Field(max_length=300)
    collapsed: bool = False
    children: list[TreeIn] = Field(default_factory=list)


def load_map(st: Storage, course_id: str, lecture_id: str) -> MapDoc:
    path = st.paths.map(course_id, lecture_id)
    if not st.exists(path):
        raise NotFound("This lecture has no map yet.")
    return st.read_doc(path, MapDoc)


def save_map(st: Storage, course_id: str, lecture_id: str, doc: MapDoc) -> None:
    st.write_doc(st.paths.map(course_id, lecture_id), doc)


def _clean_label(label: str) -> str:
    out = " ".join(label.split())
    if not out:
        raise MapEditError("Node labels can't be empty.")
    return out[:200]


def nearest_surviving(doc: MapDoc, node_id: str, alive: set[str]) -> str:
    cur = doc.nodes.get(node_id)
    seen: set[str] = set()
    while cur is not None and cur.id not in seen:
        seen.add(cur.id)
        if cur.id in alive:
            return cur.id
        cur = doc.nodes.get(cur.parent_id) if cur.parent_id else None
    return doc.root_id


def rehome(st: Storage, course_id: str, lecture_id: str, moves: dict[str, str]) -> None:
    """Move threads, recent doubts, notes and practice items from old → new node ids."""
    moves = {a: b for a, b in moves.items() if a != b}
    if not moves:
        return
    p = st.paths
    if st.exists(p.threads(course_id, lecture_id)):
        with st.update_doc(p.threads(course_id, lecture_id), ThreadsDoc) as th:
            for old, new in moves.items():
                if old in th.by_node:
                    th.by_node.setdefault(new, []).extend(th.by_node.pop(old))
    if st.exists(p.recent(course_id, lecture_id)):
        with st.update_doc(p.recent(course_id, lecture_id), RecentDoc) as rc:
            for item in rc.items:
                if item.node_id in moves:
                    item.node_id = moves[item.node_id]
    if st.exists(p.lecture_notes(course_id, lecture_id)):
        with st.update_doc(p.lecture_notes(course_id, lecture_id), NotesDoc) as nd:
            for n in nd.items:
                if n.node_id in moves:
                    n.node_id = moves[n.node_id]
    if st.exists(p.practice(course_id, lecture_id)):
        with st.update_doc(p.practice(course_id, lecture_id), PracticeDoc) as pr:
            for it in pr.items:
                if it.node_id in moves:
                    it.node_id = moves[it.node_id]


def _merge_sources(a: Iterable[SlideRef], b: Iterable[SlideRef]) -> list[SlideRef]:
    seen: dict[tuple[str, int], SlideRef] = {}
    for s in list(a) + list(b):
        seen.setdefault((s.source_id, s.slide), s)
    return sorted(seen.values(), key=lambda s: (s.source_id, s.slide))


# --------------------------------------------------------------------------- structure sync

def apply_structure(st: Storage, course_id: str, lecture_id: str, tree: TreeIn) -> MapDoc:
    """Reconcile the editor's tree with the stored map."""
    st_path = st.paths.map(course_id, lecture_id)
    with st.lock(st_path):
        doc = load_map(st, course_id, lecture_id)
        if tree.id != doc.root_id:
            raise MapEditError("The map root can't be replaced.")
        seen: set[str] = set()
        new_nodes: dict[str, Node] = {}

        def walk(t: TreeIn, parent: str | None) -> None:
            if t.id in seen:
                raise MapEditError("A node appears twice in the map.")
            seen.add(t.id)
            existing = doc.nodes.get(t.id)
            if existing is None:
                if not is_id(t.id):
                    raise MapEditError(f"Invalid node id {t.id!r}.")
                existing = Node(id=t.id, label=_clean_label(t.label), origin="user")
            node = existing.model_copy(deep=True)
            node.label = _clean_label(t.label)
            node.parent_id = parent
            node.collapsed = t.collapsed
            node.children = [c.id for c in t.children]
            new_nodes[node.id] = node
            for c in t.children:
                walk(c, node.id)

        walk(tree, None)
        alive = set(new_nodes)
        moves = {old: nearest_surviving(doc, old, alive) for old in doc.nodes if old not in alive}
        old_doc = doc
        doc = MapDoc(lecture_id=old_doc.lecture_id, root_id=old_doc.root_id, nodes=new_nodes)
        save_map(st, course_id, lecture_id, doc)
    rehome(st, course_id, lecture_id, moves)
    _refresh_coverage(st, course_id, lecture_id, doc)
    return doc


# --------------------------------------------------------------------------- single-node edits

def patch_node(
    st: Storage, course_id: str, lecture_id: str, node_id: str,
    label: str | None = None, status: Status | None = None, studied: bool = False, auto: bool = False,
) -> MapDoc:
    path = st.paths.map(course_id, lecture_id)
    with st.lock(path):
        doc = load_map(st, course_id, lecture_id)
        node = doc.nodes.get(node_id)
        if node is None:
            raise NotFound("node not found")
        if label is not None:
            node.label = _clean_label(label)
        if status is not None:
            node.status = status
            node.status_mode = "manual"
        if auto:
            node.status_mode = "auto"
        if studied:
            node.last_studied_at = now_iso()
        save_map(st, course_id, lecture_id, doc)
    return doc


def add_nodes(
    st: Storage, course_id: str, lecture_id: str, parent_id: str,
    parts: list[tuple[str, list[SlideRef]]], origin: str = "user", index: int | None = None,
) -> tuple[MapDoc, list[str]]:
    path = st.paths.map(course_id, lecture_id)
    with st.lock(path):
        doc = load_map(st, course_id, lecture_id)
        parent = doc.nodes.get(parent_id)
        if parent is None:
            raise NotFound("node not found")
        ids = []
        for i, (label, sources) in enumerate(parts):
            n = Node(id=new_id(), label=_clean_label(label), parent_id=parent_id, sources=sources,
                     origin="ai" if origin == "ai" else "user")
            doc.nodes[n.id] = n
            if index is None:
                parent.children.append(n.id)
            else:
                parent.children.insert(index + i, n.id)
            ids.append(n.id)
        parent.collapsed = False
        save_map(st, course_id, lecture_id, doc)
    _refresh_coverage(st, course_id, lecture_id, doc)
    return doc, ids


def split_node(
    st: Storage, course_id: str, lecture_id: str, node_id: str, parts: list[tuple[str, list[SlideRef]]],
) -> MapDoc:
    """The first part keeps the node's id (and its children, threads, cards);
    the others become new siblings right after it."""
    if len(parts) < 2:
        raise MapEditError("A split needs at least two parts.")
    path = st.paths.map(course_id, lecture_id)
    with st.lock(path):
        doc = load_map(st, course_id, lecture_id)
        node = doc.nodes.get(node_id)
        if node is None or node.parent_id is None:
            raise MapEditError("This node can't be split.")
        parent = doc.nodes[node.parent_id]
        first_label, first_sources = parts[0]
        node.label = _clean_label(first_label)
        node.sources = first_sources or node.sources
        idx = parent.children.index(node.id)
        for j, (label, sources) in enumerate(parts[1:], 1):
            n = Node(id=new_id(), label=_clean_label(label), parent_id=parent.id, sources=sources, origin="ai")
            doc.nodes[n.id] = n
            parent.children.insert(idx + j, n.id)
        save_map(st, course_id, lecture_id, doc)
    _refresh_coverage(st, course_id, lecture_id, doc)
    return doc


def merge_nodes(st: Storage, course_id: str, lecture_id: str, keep_id: str, other_id: str, label: str) -> MapDoc:
    path = st.paths.map(course_id, lecture_id)
    with st.lock(path):
        doc = load_map(st, course_id, lecture_id)
        keep, other = doc.nodes.get(keep_id), doc.nodes.get(other_id)
        if keep is None or other is None:
            raise NotFound("node not found")
        if keep.parent_id != other.parent_id or keep.parent_id is None:
            raise MapEditError("Only siblings can be merged.")
        keep.label = _clean_label(label)
        keep.sources = _merge_sources(keep.sources, other.sources)
        for c in other.children:
            doc.nodes[c].parent_id = keep.id
            keep.children.append(c)
        parent = doc.nodes[keep.parent_id]
        parent.children = [c for c in parent.children if c != other_id]
        del doc.nodes[other_id]
        save_map(st, course_id, lecture_id, doc)
    rehome(st, course_id, lecture_id, {other_id: keep_id})
    _refresh_coverage(st, course_id, lecture_id, doc)
    return doc


# --------------------------------------------------------------------------- coverage

def _slide_title(text: str, n: int) -> str:
    first = text.strip().splitlines()[0] if text.strip() else ""
    words = first.split()[:6]
    return " ".join(words) if words else f"Slide {n}"


def _refresh_coverage(st: Storage, course_id: str, lecture_id: str, doc: MapDoc) -> None:
    lec = get_lecture(st, course_id, lecture_id)
    if not lec.uncovered_slides:
        return
    referenced = {(s.source_id, s.slide) for n in doc.nodes.values() for s in n.sources}
    still = [u for u in lec.uncovered_slides if (u.source_id, u.slide) not in referenced]
    if len(still) != len(lec.uncovered_slides):
        update_lecture(st, course_id, lecture_id, uncovered_slides=still)


def add_uncovered(st: Storage, course_id: str, lecture_id: str) -> MapDoc:
    """'Add them?' — one node per uncovered slide under the root, labelled by the slide title."""
    lec = get_lecture(st, course_id, lecture_id)
    doc = load_map(st, course_id, lecture_id)
    if not lec.uncovered_slides:
        return doc
    texts: dict[tuple[str, int], str] = {}
    for sid in {u.source_id for u in lec.uncovered_slides}:
        cache = st.paths.slides_json(course_id, sid)
        if st.exists(cache):
            for s in st.read_doc(cache, SlidesDoc).slides:
                texts[(sid, s.number)] = s.text
    parts = [(_slide_title(texts.get((u.source_id, u.slide), ""), u.slide), [u]) for u in lec.uncovered_slides]
    doc, _ = add_nodes(st, course_id, lecture_id, doc.root_id, parts, origin="user")
    update_lecture(st, course_id, lecture_id, uncovered_slides=[])
    return doc


TreeIn.model_rebuild()
