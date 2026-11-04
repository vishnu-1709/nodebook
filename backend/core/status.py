"""Performance-based node status (SPEC §5.14). All tunable numbers live here.

A node is `auto` by default; once it has ≥ MIN_RESULTS results its status follows:
  got_it   — last 3 recall results each ≥ 80 % and no Again in the last 2 reviews
  confused — last 2 results each < 50 %, or ≥ 2 Agains within a week
  revising — otherwise
Setting a status by hand switches the node to `manual` (until the user picks automatic again)."""

from __future__ import annotations

from datetime import datetime, timedelta

from pydantic import BaseModel

from backend.core.clock import now
from backend.core.schemas import MapDoc, ResultRecord, Status
from backend.core.storage import Storage

MIN_RESULTS = 3
GOT_IT_LAST_N = 3
GOT_IT_MIN_SCORE = 0.8
GOT_IT_NO_AGAIN_IN_LAST = 2
CONFUSED_LAST_N = 2
CONFUSED_MAX_SCORE = 0.5
CONFUSED_AGAINS = 2
CONFUSED_AGAIN_WINDOW = timedelta(days=7)
AGAIN = 1


class ReviewRow(BaseModel):
    node_id: str | None = None
    rating: int
    reviewed_at: str


class StatusReason(BaseModel):
    status: Status
    results: int
    reason: str


def decide(results: list[ResultRecord], reviews: list[ReviewRow], at: datetime | None = None) -> StatusReason | None:
    """Pure rule. `results` and `reviews` are for one node, oldest first. None = not enough data."""
    at = at or now()
    if len(results) < MIN_RESULTS:
        return None
    scores = [r.score for r in results]
    ratings = [r.rating for r in reviews]
    week_agains = sum(
        1 for r in reviews if r.rating == AGAIN and datetime.fromisoformat(r.reviewed_at) >= at - CONFUSED_AGAIN_WINDOW
    )
    last_conf = scores[-CONFUSED_LAST_N:]
    if (len(last_conf) == CONFUSED_LAST_N and all(s < CONFUSED_MAX_SCORE for s in last_conf)) or week_agains >= CONFUSED_AGAINS:
        why = f"{week_agains} “Again” ratings this week" if week_agains >= CONFUSED_AGAINS else "your last 2 results were under 50%"
        return StatusReason(status="confused", results=len(results), reason=f"Confused: {why}.")
    last_got = scores[-GOT_IT_LAST_N:]
    if all(s >= GOT_IT_MIN_SCORE for s in last_got) and AGAIN not in ratings[-GOT_IT_NO_AGAIN_IN_LAST:]:
        return StatusReason(status="got_it", results=len(results), reason="Got it: your last 3 results were 80% or better.")
    return StatusReason(status="revising", results=len(results), reason="Revising: mixed recent results.")


def node_evidence(st: Storage, course_id: str, lecture_id: str, node_id: str) -> tuple[list[ResultRecord], list[ReviewRow]]:
    results = [r for r in st.read_jsonl(st.paths.results(course_id, lecture_id), ResultRecord) if r.node_id == node_id]
    results.sort(key=lambda r: r.created_at)
    reviews = [r for r in st.read_jsonl(st.paths.review_log(course_id), ReviewRow) if r.node_id == node_id]
    reviews.sort(key=lambda r: r.reviewed_at)
    return results, reviews


def recompute(st: Storage, course_id: str, lecture_id: str, node_ids: list[str] | None = None) -> dict[str, Status]:
    """Re-apply the rule to auto nodes (all, or the given ones). Returns changed statuses."""
    path = st.paths.map(course_id, lecture_id)
    if not st.exists(path):
        return {}
    changed: dict[str, Status] = {}
    with st.update_doc(path, MapDoc) as doc:
        for nid in node_ids or list(doc.nodes):
            node = doc.nodes.get(nid)
            if node is None or node.status_mode != "auto" or nid == doc.root_id:
                continue
            res, rev = node_evidence(st, course_id, lecture_id, nid)
            d = decide(res, rev)
            if d and d.status != node.status:
                node.status = d.status
                changed[nid] = d.status
    return changed


def explain(st: Storage, course_id: str, lecture_id: str, node_id: str) -> StatusReason | None:
    res, rev = node_evidence(st, course_id, lecture_id, node_id)
    return decide(res, rev)
