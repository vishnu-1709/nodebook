"""Node Q&A threads (SPEC §5.5).

New exchanges are temporary (recent.json, expire after 7 days) unless the user
keeps them (threads.json, never expire) or has "keep all questions" on."""

from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel

from backend.core.clock import now, now_iso
from backend.core.courses import NotFound, list_courses, list_lectures
from backend.core.schemas import Exchange, Message, RecentDoc, RecentExchange, ThreadsDoc
from backend.core.storage import Storage

RECENT_DAYS = 7


class NodeThread(BaseModel):
    kept: list[Exchange]
    recent: list[RecentExchange]


def _expires() -> str:
    return (now() + timedelta(days=RECENT_DAYS)).isoformat(timespec="seconds")


def _expired(item: RecentExchange, at: datetime | None = None) -> bool:
    try:
        return datetime.fromisoformat(item.expires_at) <= (at or now())
    except ValueError:
        return True


def purge_expired(st: Storage, course_id: str, lecture_id: str) -> int:
    path = st.paths.recent(course_id, lecture_id)
    if not st.exists(path):
        return 0
    with st.update_doc(path, RecentDoc) as doc:
        before = len(doc.items)
        doc.items = [i for i in doc.items if not _expired(i)]
        return before - len(doc.items)


def purge_all_expired(st: Storage) -> int:
    """Run at startup: temporary doubts older than 7 days are gone on next launch."""
    total = 0
    for c in list_courses(st):
        for lec in list_lectures(st, c.id):
            total += purge_expired(st, c.id, lec.id)
    return total


def node_thread(st: Storage, course_id: str, lecture_id: str, node_id: str) -> NodeThread:
    p = st.paths
    kept = st.read_doc(p.threads(course_id, lecture_id), ThreadsDoc, ThreadsDoc).by_node.get(node_id, [])
    recent = [
        r for r in st.read_doc(p.recent(course_id, lecture_id), RecentDoc, RecentDoc).items
        if r.node_id == node_id and not _expired(r)
    ]
    recent.sort(key=lambda r: r.created_at, reverse=True)
    return NodeThread(kept=kept, recent=recent)


def kept_counts(st: Storage, course_id: str, lecture_id: str) -> dict[str, int]:
    doc = st.read_doc(st.paths.threads(course_id, lecture_id), ThreadsDoc, ThreadsDoc)
    return {k: len(v) for k, v in doc.by_node.items() if v}


def last_kept(st: Storage, course_id: str, lecture_id: str, node_id: str, n: int = 3) -> list[Exchange]:
    kept = st.read_doc(st.paths.threads(course_id, lecture_id), ThreadsDoc, ThreadsDoc).by_node.get(node_id, [])
    return kept[-n:]


def find_exchange(st: Storage, course_id: str, lecture_id: str, exchange_id: str) -> tuple[str, Exchange, bool]:
    """Returns (node_id, exchange, is_kept)."""
    p = st.paths
    th = st.read_doc(p.threads(course_id, lecture_id), ThreadsDoc, ThreadsDoc)
    for node_id, items in th.by_node.items():
        for ex in items:
            if ex.id == exchange_id:
                return node_id, ex, True
    for r in st.read_doc(p.recent(course_id, lecture_id), RecentDoc, RecentDoc).items:
        if r.id == exchange_id:
            return r.node_id, r, False
    raise NotFound("exchange not found")


def start_exchange(st: Storage, course_id: str, lecture_id: str, node_id: str, keep: bool) -> Exchange:
    p = st.paths
    if keep:
        ex = Exchange(kept_at=now_iso())
        with st.update_doc(p.threads(course_id, lecture_id), ThreadsDoc, ThreadsDoc) as th:
            th.by_node.setdefault(node_id, []).append(ex)
        return ex
    rex = RecentExchange(node_id=node_id, expires_at=_expires())
    with st.update_doc(p.recent(course_id, lecture_id), RecentDoc, RecentDoc) as rc:
        rc.items.append(rex)
    return rex


def append_messages(st: Storage, course_id: str, lecture_id: str, exchange_id: str, messages: list[Message]) -> Exchange:
    p = st.paths
    with st.lock(p.threads(course_id, lecture_id)), st.lock(p.recent(course_id, lecture_id)):
        with st.update_doc(p.threads(course_id, lecture_id), ThreadsDoc, ThreadsDoc) as th:
            for items in th.by_node.values():
                for ex in items:
                    if ex.id == exchange_id:
                        ex.messages.extend(messages)
                        return ex
        with st.update_doc(p.recent(course_id, lecture_id), RecentDoc, RecentDoc) as rc:
            for r in rc.items:
                if r.id == exchange_id:
                    r.messages.extend(messages)
                    r.expires_at = _expires()  # an active doubt stays around
                    return r
    raise NotFound("exchange not found")


def keep(st: Storage, course_id: str, lecture_id: str, exchange_id: str) -> Exchange:
    p = st.paths
    with st.lock(p.threads(course_id, lecture_id)), st.lock(p.recent(course_id, lecture_id)):
        node_id, ex, is_kept = find_exchange(st, course_id, lecture_id, exchange_id)
        if is_kept:
            return ex
        with st.update_doc(p.recent(course_id, lecture_id), RecentDoc, RecentDoc) as rc:
            rc.items = [r for r in rc.items if r.id != exchange_id]
        kept = Exchange(id=ex.id, created_at=ex.created_at, kept_at=now_iso(), messages=ex.messages)
        with st.update_doc(p.threads(course_id, lecture_id), ThreadsDoc, ThreadsDoc) as th:
            th.by_node.setdefault(node_id, []).append(kept)
        return kept


def unkeep(st: Storage, course_id: str, lecture_id: str, exchange_id: str) -> RecentExchange:
    p = st.paths
    with st.lock(p.threads(course_id, lecture_id)), st.lock(p.recent(course_id, lecture_id)):
        node_id, ex, is_kept = find_exchange(st, course_id, lecture_id, exchange_id)
        if not is_kept:
            assert isinstance(ex, RecentExchange)
            return ex
        with st.update_doc(p.threads(course_id, lecture_id), ThreadsDoc, ThreadsDoc) as th:
            th.by_node[node_id] = [e for e in th.by_node.get(node_id, []) if e.id != exchange_id]
            if not th.by_node[node_id]:
                del th.by_node[node_id]
        rex = RecentExchange(id=ex.id, created_at=ex.created_at, messages=ex.messages, node_id=node_id,
                             expires_at=_expires())
        with st.update_doc(p.recent(course_id, lecture_id), RecentDoc, RecentDoc) as rc:
            rc.items.append(rex)
        return rex


def delete_exchange(st: Storage, course_id: str, lecture_id: str, exchange_id: str) -> None:
    p = st.paths
    node_id, _, is_kept = find_exchange(st, course_id, lecture_id, exchange_id)
    if is_kept:
        with st.update_doc(p.threads(course_id, lecture_id), ThreadsDoc, ThreadsDoc) as th:
            th.by_node[node_id] = [e for e in th.by_node.get(node_id, []) if e.id != exchange_id]
            if not th.by_node[node_id]:
                del th.by_node[node_id]
    else:
        with st.update_doc(p.recent(course_id, lecture_id), RecentDoc, RecentDoc) as rc:
            rc.items = [r for r in rc.items if r.id != exchange_id]
