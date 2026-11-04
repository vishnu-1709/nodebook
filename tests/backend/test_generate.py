from __future__ import annotations

from fastapi.testclient import TestClient

from backend.core.schemas import PracticeDoc
from tests.backend.helpers import DECKS, find, lecture_with_map, to_tree


def setup(client: TestClient, ctx):  # noqa: ANN001, ANN201
    cid, lid, m = lecture_with_map(client, ctx)
    return cid, lid, m, f"/api/courses/{cid}/generate"


def test_generate_question_with_sources_and_suggestion(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, m, base = setup(client, ctx)
    it = client.post(base, json={"type": "questions", "lecture_ids": [lid]}).json()
    assert it["front"] and it["back"] and it["sources"]
    assert it["suggested"]["course_id"] == cid
    assert it["key"]


def test_next_never_repeats(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, m, base = setup(client, ctx)
    seen: list[str] = []
    for _ in range(6):
        r = client.post(base, json={"type": "flashcards", "lecture_ids": [lid], "exclude": seen})
        assert r.status_code == 200, r.text
        it = r.json()
        assert it["key"] not in seen
        seen.append(it["key"])
    assert len(set(seen)) == 6


def test_repeat_from_model_is_rejected(client: TestClient, ctx, fake) -> None:  # noqa: ANN001
    cid, lid, m, base = setup(client, ctx)
    fake.handlers["generate_questions"] = lambda messages, schema: {"front": "Same?", "back": "x", "cites": []}
    first = client.post(base, json={"type": "questions", "lecture_ids": [lid]}).json()
    r = client.post(base, json={"type": "questions", "lecture_ids": [lid], "exclude": [first["key"]]})
    assert r.status_code == 502 and "new item" in r.json()["detail"]


def test_pyq_style_ref(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, m, base = setup(client, ctx)
    with open(DECKS / "linear_regression.pdf", "rb") as fh:
        src = client.post(f"/api/courses/{cid}/sources", files={"file": ("pyq_2023.pdf", fh)}, data={"kind": "pyq"}).json()
    it = client.post(base, json={"type": "questions", "source_ids": [src["id"]]}).json()
    assert "PYQ" in it["ref"]


def test_save_question_appears_on_node(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, m, base = setup(client, ctx)
    nid = find(to_tree(m), "Ridge regression")["id"]
    it = client.post(base, json={"type": "questions", "lecture_ids": [lid]}).json()
    dest = {"course_id": cid, "lecture_id": lid, "node_id": nid, "label": "Ridge"}
    saved = client.post(f"{base}/save", json={"item": it, "destination": dest}).json()
    assert saved["kind"] == "practice"
    items = client.get(f"/api/courses/{cid}/lectures/{lid}/practice", params={"node_id": nid}).json()
    assert len(items) == 1
    p = items[0]
    assert p["type"] == "question" and p["answer_status"] == "ai_unverified"
    assert p["origin"]["kind"] == "generate" and p["origin"]["source_ids"]


def test_save_unassigned_course_level(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, m, base = setup(client, ctx)
    it = client.post(base, json={"type": "flashcards", "lecture_ids": [lid]}).json()
    client.post(f"{base}/save", json={"item": it, "destination": {"course_id": cid, "label": "Course"}})
    doc = ctx.storage.read_doc(ctx.storage.paths.course_practice(cid), PracticeDoc)
    assert len(doc.items) == 1 and doc.items[0].node_id is None


def test_save_summary_and_explanation(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, m, base = setup(client, ctx)
    nid = find(to_tree(m), "Normal equations")["id"]
    dest = {"course_id": cid, "lecture_id": lid, "node_id": nid, "label": "x"}
    s = client.post(base, json={"type": "summary", "lecture_ids": [lid]}).json()
    assert client.post(f"{base}/save", json={"item": s, "destination": dest}).json()["kind"] == "note"
    assert client.get(f"/api/courses/{cid}/lectures/{lid}/notes", params={"node_id": nid}).json()
    e = client.post(base, json={"type": "explain", "lecture_ids": [lid], "topic": "normal equations"}).json()
    assert client.post(f"{base}/save", json={"item": e, "destination": dest}).json()["kind"] == "exchange"
    th = client.get(f"/api/courses/{cid}/lectures/{lid}/nodes/{nid}/thread").json()
    assert len(th["kept"]) == 1
    # lecture-level summary when no node
    client.post(f"{base}/save", json={"item": s, "destination": {"course_id": cid, "lecture_id": lid, "label": "L"}})
    assert any(n["node_id"] is None for n in client.get(f"/api/courses/{cid}/lectures/{lid}/notes").json())


def test_check_answer_and_validation(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, m, base = setup(client, ctx)
    it = client.post(base, json={"type": "questions", "lecture_ids": [lid]}).json()
    g = client.post(f"{base}/check", json={"question": it["front"], "reference": it["back"],
                                           "answer": "the gradient is zero at the optimum", "sources": it["sources"]}).json()
    assert g["verdict"] == "correct"
    assert client.post(base, json={"type": "explain", "lecture_ids": [lid]}).status_code == 400
    assert client.post(base, json={"type": "questions"}).status_code == 400
    dests = client.get(f"{base}/destinations").json()
    assert dests[0]["label"].startswith("Course") and len(dests) > 5
