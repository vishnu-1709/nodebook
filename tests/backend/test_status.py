from __future__ import annotations

import json
from datetime import timedelta

from fastapi.testclient import TestClient

from backend.core.clock import now
from backend.core.schemas import MapDoc, ResultRecord
from backend.core.status import ReviewRow, decide
from tests.backend.helpers import find, lecture_with_map, to_tree


def res(*scores: float) -> list[ResultRecord]:
    return [ResultRecord(node_id="n", kind="recall", score=s) for s in scores]


def rev(*ratings: int, days_ago: float = 0) -> list[ReviewRow]:
    t = (now() - timedelta(days=days_ago)).isoformat()
    return [ReviewRow(node_id="n", rating=r, reviewed_at=t) for r in ratings]


def test_rules() -> None:
    assert decide(res(1, 1), []) is None  # < 3 results: no auto status
    assert decide(res(0.2, 0.9, 0.8, 1.0), []).status == "got_it"
    assert decide(res(0.9, 0.9, 0.9), rev(3, 1)).status == "revising"  # Again in last 2 reviews blocks got_it
    assert decide(res(0.9, 0.4, 0.3), []).status == "confused"  # last 2 < 50 %
    assert decide(res(0.9, 0.9, 0.9), rev(1, 1, 3, 3)).status == "confused"  # 2 Agains this week
    assert decide(res(0.9, 0.9, 0.9), rev(1, 1, days_ago=10) + rev(3, 3)).status == "got_it"  # old Agains don't count
    assert decide(res(0.6, 0.7, 0.5), []).status == "revising"


def test_v1_map_migrates_status_mode(tmp_path, client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, m = lecture_with_map(client, ctx)
    st = ctx.storage
    path = st.paths.map(cid, lid)
    raw = json.loads(path.read_text())
    raw["schema"] = 1
    ids = list(raw["nodes"])
    for n in raw["nodes"].values():
        n["status_mode"] = "manual"
    raw["nodes"][ids[1]]["status"] = "got_it"
    path.write_text(json.dumps(raw))
    doc = st.read_doc(path, MapDoc)
    assert doc.nodes[ids[1]].status_mode == "manual"  # user-set status stays manual
    assert doc.nodes[ids[2]].status_mode == "auto"
    assert json.loads(path.read_text())["schema"] == 2  # rewritten


def test_auto_status_follows_results_and_manual_override(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, m = lecture_with_map(client, ctx)
    nid = find(to_tree(m), "Ridge regression")["id"]
    base = f"/api/courses/{cid}/lectures/{lid}"
    good = [{"question": "q", "answer": "a", "verdict": "correct", "feedback": "", "source": None}] * 3
    for _ in range(3):
        client.post(f"{base}/nodes/{nid}/test-me/save", json={"results": good})
    node = client.get(f"{base}/map").json()["nodes"][nid]
    assert node["status"] == "got_it" and node["status_mode"] == "auto"
    why = client.get(f"{base}/nodes/{nid}/status").json()
    assert why["reason"].startswith("Got it") and why["results"] == 3
    # two bad results → confused
    bad = [{"question": "q", "answer": "", "verdict": "wrong", "feedback": "", "source": None}]
    client.post(f"{base}/nodes/{nid}/test-me/save", json={"results": bad})
    client.post(f"{base}/nodes/{nid}/test-me/save", json={"results": bad})
    assert client.get(f"{base}/map").json()["nodes"][nid]["status"] == "confused"
    # manual override sticks
    client.patch(f"{base}/map/nodes/{nid}", json={"status": "revising"})
    client.post(f"{base}/nodes/{nid}/test-me/save", json={"results": good})
    node = client.get(f"{base}/map").json()["nodes"][nid]
    assert node["status"] == "revising" and node["status_mode"] == "manual"
    # back to automatic
    n2 = client.patch(f"{base}/map/nodes/{nid}", json={"status_mode": "auto"}).json()["nodes"][nid]
    assert n2["status_mode"] == "auto" and n2["status"] == "revising"


def test_agains_in_review_make_confused(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, m = lecture_with_map(client, ctx)
    nid = find(to_tree(m), "Lasso regression")["id"]
    base = f"/api/courses/{cid}/lectures/{lid}"
    good = [{"question": "q", "answer": "a", "verdict": "correct", "feedback": "", "source": None}]
    for _ in range(3):
        client.post(f"{base}/nodes/{nid}/test-me/save", json={"results": good})
    card = client.post(f"{base}/practice", json={"type": "card", "node_id": nid, "front": "F", "back": "B"}).json()
    for _ in range(2):
        client.post("/api/review/rate", json={"course_id": cid, "lecture_id": lid, "item_id": card["id"], "rating": 1})
    assert client.get(f"{base}/map").json()["nodes"][nid]["status"] == "confused"
