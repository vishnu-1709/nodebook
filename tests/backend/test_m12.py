from __future__ import annotations

from datetime import datetime, timedelta

from fastapi.testclient import TestClient

from backend.core.clock import now
from backend.core.review import rate
from backend.core.today import build_today
from tests.backend.helpers import find, lecture_with_map, to_tree


def test_ics_export(client: TestClient) -> None:
    due = (datetime.now().astimezone() + timedelta(days=2)).isoformat(timespec="minutes")
    r = client.post("/api/reminders", json={"text": "Lab exam, room 4; bring ID", "due_at": due, "tags": ["exam"]}).json()
    one = client.get(f"/api/reminders/{r['id']}.ics")
    assert one.status_code == 200 and one.headers["content-type"].startswith("text/calendar")
    body = one.text
    assert body.startswith("BEGIN:VCALENDAR\r\n") and "BEGIN:VEVENT" in body and body.endswith("END:VCALENDAR\r\n")
    assert r"SUMMARY:Lab exam\, room 4\; bring ID #exam" in body and f"UID:{r['id']}@nodebook.local" in body
    assert all(len(line.encode()) <= 75 for line in body.split("\r\n"))
    assert client.get("/api/reminders.ics").text.count("BEGIN:VEVENT") == 1


def test_today_v02_due_fading_week(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, m = lecture_with_map(client, ctx)
    nid = find(to_tree(m), "Ridge regression")["id"]
    base = f"/api/courses/{cid}/lectures/{lid}"
    ids = [client.post(f"{base}/practice", json={"type": "card", "node_id": nid, "front": f"F{i}", "back": "B"}).json()["id"] for i in range(3)]
    t0 = now()
    rate(ctx.storage, cid, lid, ids[0], 3, at=t0 - timedelta(days=1))  # short interval → due again soon / fading
    rate(ctx.storage, cid, lid, ids[1], 4, at=t0)  # long interval → not fading
    client.post("/api/sessions", json={"started_at": (t0 - timedelta(hours=2)).isoformat(), "ended_at": (t0 - timedelta(hours=1, minutes=35)).isoformat(), "work_min": 25})
    t = build_today(ctx.storage, t0)
    counts = client.get("/api/review/counts").json()
    assert t.due == counts["total"]  # due count matches the queue
    assert t.week.reviews == 2 and t.week.focus_min == 25 and t.week.sessions == 1
    assert all(f.count >= 1 for f in t.fading)


def test_brain_check(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, m = lecture_with_map(client, ctx)
    tree = to_tree(m)
    a, b = find(tree, "Normal equations")["id"], find(tree, "Ridge regression")["id"]
    card = client.post(f"/api/courses/{cid}/lectures/{lid}/practice", json={"type": "card", "node_id": a, "front": "F", "back": "B"}).json()
    start = now() - timedelta(minutes=25)
    client.post("/api/review/rate", json={"course_id": cid, "lecture_id": lid, "item_id": card["id"], "rating": 3})
    r = client.post("/api/brain-check", json={
        "nodes": [{"course_id": cid, "lecture_id": lid, "node_id": a}, {"course_id": cid, "lecture_id": lid, "node_id": b},
                  {"course_id": cid, "lecture_id": lid, "node_id": a}],
        "started_at": start.isoformat(), "ended_at": now().isoformat(), "work_min": 25}).json()
    assert r["summary"] == "25 min · 2 nodes · 1 card"
    assert len(r["questions"]) == 3 and {q["node_id"] for q in r["questions"]} == {a, b}
    empty = client.post("/api/brain-check", json={"nodes": [], "started_at": start.isoformat(), "ended_at": now().isoformat(), "work_min": 25}).json()
    assert empty["questions"] == [] and empty["summary"].startswith("25 min · 0 nodes")
