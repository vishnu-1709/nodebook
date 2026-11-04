from __future__ import annotations

import io
import json
import zipfile
from datetime import timedelta

from fastapi.testclient import TestClient

from backend.core.clock import now
from backend.core.review import queue, rate
from tests.backend.helpers import find, lecture_with_map, to_tree


def seed(client: TestClient, ctx):  # noqa: ANN001, ANN201
    cid, lid, m = lecture_with_map(client, ctx)
    nid = find(to_tree(m), "Normal equations")["id"]
    base = f"/api/courses/{cid}/lectures/{lid}"
    ids = []
    for i in range(3):
        ids.append(client.post(f"{base}/practice", json={"type": "card", "node_id": nid, "front": f"Q{i}", "back": f"A{i}"}).json()["id"])
    return cid, lid, nid, base, ids


def test_ratings_update_fsrs_and_review_log(client: TestClient, ctx) -> None:  # noqa: ANN001
    """AC 5.12: ratings update fsrs state and review_log.jsonl."""
    cid, lid, nid, base, ids = seed(client, ctx)
    q = client.get("/api/review/queue", params={"course_id": cid}).json()
    assert q["total"] == 3
    assert set(q["items"][0]["intervals"]) == {"1", "2", "3", "4"}
    assert q["items"][0]["node_label"] == "Normal equations"
    r = client.post("/api/review/rate", json={"course_id": cid, "lecture_id": lid, "item_id": ids[0], "rating": 3, "duration_ms": 4200}).json()
    assert r["item"]["fsrs"]["due"] and r["remaining"] == 2
    log = [json.loads(x) for x in ctx.storage.paths.review_log(cid).read_text().splitlines()]
    assert log[0]["item_id"] == ids[0] and log[0]["rating"] == 3 and log[0]["duration_ms"] == 4200
    practice = client.get(f"{base}/practice", params={"node_id": nid}).json()
    assert next(p for p in practice if p["id"] == ids[0])["fsrs"]["state"] in (1, 2)


def test_due_counts_match_queue(client: TestClient, ctx) -> None:  # noqa: ANN001
    """AC 5.12: due counts on Today match the queue."""
    cid, lid, nid, base, ids = seed(client, ctx)
    client.post("/api/review/rate", json={"course_id": cid, "lecture_id": lid, "item_id": ids[1], "rating": 4})
    counts = client.get("/api/review/counts").json()
    q = client.get("/api/review/queue", params={"course_id": cid}).json()
    assert counts["total"] == q["total"] == 2 and counts["by_course"][cid] == 2
    assert len(client.get("/api/review/queue").json()["items"]) == 2  # all courses


def test_again_comes_back_soon_easy_goes_far(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, nid, base, ids = seed(client, ctx)
    t = now()
    rate(ctx.storage, cid, lid, ids[0], 1, at=t)
    rate(ctx.storage, cid, lid, ids[1], 4, at=t)
    due_soon = {r.item.id for r in queue(ctx.storage, cid, at=t + timedelta(minutes=15))}
    assert ids[0] in due_soon and ids[1] not in due_soon
    later = {r.item.id for r in queue(ctx.storage, cid, at=t + timedelta(days=30))}
    assert ids[1] in later


def test_lecture_filter_and_course_level_items(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, nid, base, ids = seed(client, ctx)
    gen = f"/api/courses/{cid}/generate"
    it = client.post(gen, json={"type": "flashcards", "lecture_ids": [lid]}).json()
    client.post(f"{gen}/save", json={"item": it, "destination": {"course_id": cid, "label": "Course"}})
    assert client.get("/api/review/queue", params={"course_id": cid}).json()["total"] == 4
    assert client.get("/api/review/queue", params={"course_id": cid, "lecture_id": lid}).json()["total"] == 3
    course_item = next(i for i in client.get("/api/review/queue", params={"course_id": cid}).json()["items"] if i["lecture_id"] is None)
    r = client.post("/api/review/rate", json={"course_id": cid, "lecture_id": None, "item_id": course_item["item"]["id"], "rating": 2})
    assert r.status_code == 200


def test_practice_crud_and_card_sources(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, nid, base, ids = seed(client, ctx)
    assert client.patch(f"{base}/practice/{ids[0]}", json={"front": "Edited"}).json()["front"] == "Edited"
    assert client.delete(f"{base}/practice/{ids[1]}").status_code == 204
    cards = client.post(f"{base}/nodes/{nid}/practice/cards").json()
    assert cards and all(c["origin"]["kind"] == "node" and c["node_id"] == nid for c in cards)
    again = client.post(f"{base}/nodes/{nid}/practice/cards")
    assert again.status_code == 502  # no new cards left from this small node — plain message
    note = client.post(f"{base}/notes", json={"text": "XᵀX must be invertible", "node_id": nid}).json()
    from_note = client.post(f"{base}/notes/{note['id']}/to-card").json()
    assert from_note[0]["origin"]["kind"] == "note" and from_note[0]["node_id"] == nid


def test_anki_export(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, nid, base, ids = seed(client, ctx)
    r = client.get(f"/api/courses/{cid}/anki")
    assert r.status_code == 200 and r.headers["content-disposition"].endswith('.apkg"')
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert any(n.startswith("collection.anki2") for n in z.namelist())
    r2 = client.get(f"/api/courses/{cid}/anki", params={"lecture_id": lid})
    assert r2.status_code == 200
