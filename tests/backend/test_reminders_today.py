from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.core.reminders import parse_reminder
from backend.core.today import build_today
from tests.backend.helpers import find, lecture_with_map, to_tree

NOW = datetime(2026, 11, 4, 18, 0, tzinfo=timezone.utc)


def test_ac_lab_exam_parse() -> None:
    """AC 5.10: "lab exam 14 nov #exam" → due Nov 14, tag exam."""
    r = parse_reminder("lab exam 14 nov #exam", NOW)
    d = datetime.fromisoformat(r.due_at)
    assert (d.year, d.month, d.day, d.hour) == (2026, 11, 14, 9)
    assert r.tags == ["exam"] and r.text == "lab exam 14 nov"


def test_parse_variants() -> None:
    r = parse_reminder("submit assignment friday 5pm #assignment #Lab", NOW)
    d = datetime.fromisoformat(r.due_at)
    assert (d.month, d.day, d.hour) == (11, 6, 17) and r.tags == ["assignment", "lab"]
    r = parse_reminder("quiz tomorrow", NOW)
    assert datetime.fromisoformat(r.due_at).day == 5
    r = parse_reminder("revise chapter 3 #revise", NOW)
    assert r.due_at is None and r.tags == ["revise"]
    r = parse_reminder("midsem 2 feb #exam", NOW)
    assert datetime.fromisoformat(r.due_at).year == 2027  # past date → next year


def test_reminder_crud_and_custom_tags(client: TestClient) -> None:
    due = (datetime.now().astimezone() + timedelta(days=3)).isoformat(timespec="minutes")
    r = client.post("/api/reminders", json={"text": "Lab report", "due_at": due, "tags": ["lab", "physics"]}).json()
    body = client.get("/api/reminders").json()
    assert [i["id"] for i in body["items"]] == [r["id"]]
    assert [t["name"] for t in body["custom_tags"]] == ["physics"] and "exam" in body["builtin_tags"]
    assert client.patch(f"/api/reminders/{r['id']}", json={"done": True}).json()["done"] is True
    assert client.put("/api/reminders/tags", json={"name": "physics", "colour": "tag-4"}).json()[0]["colour"] == "tag-4"
    assert client.post("/api/reminders", json={"text": "x", "due_at": "not a date"}).status_code == 400
    assert client.delete(f"/api/reminders/{r['id']}").status_code == 204
    assert client.post("/api/reminders/parse", json={"text": "quiz tomorrow #quiz"}).json()["tags"] == ["quiz"]


def test_today_empty(client: TestClient) -> None:
    t = client.get("/api/today").json()
    assert t["has_courses"] is False and t["exam"] is None


def test_today_buckets_countdown_weak_progress(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, m = lecture_with_map(client, ctx)
    nid = find(to_tree(m), "Ridge regression")["id"]
    client.patch(f"/api/courses/{cid}/lectures/{lid}/map/nodes/{nid}", json={"status": "confused"})
    now = datetime.now().astimezone()
    for text, delta, tags in [("old", -2, []), ("later today", 0.01, []), ("soon", 3, []),
                              ("lab exam", 10, ["exam"]), ("far", 30, [])]:
        client.post("/api/reminders", json={"text": text, "due_at": (now + timedelta(days=delta)).isoformat(), "tags": tags})
    t = build_today(ctx.storage, now)
    assert [r.text for r in t.overdue] == ["old"]
    assert [r.text for r in t.upcoming] == ["soon"]
    assert t.exam and t.exam.reminder.text == "lab exam" and t.exam.days == 10
    assert [w.label for w in t.weak_nodes] == ["Ridge regression"]
    assert t.progress[0].confused == 1 and t.current_course_id == cid


def test_session_log(client: TestClient, ctx) -> None:  # noqa: ANN001
    client.post("/api/sessions", json={"started_at": "2026-11-04T10:00", "ended_at": "2026-11-04T10:25", "work_min": 25})
    assert ctx.storage.paths.sessions.read_text().count("\n") == 1
