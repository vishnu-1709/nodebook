from __future__ import annotations

import time

from fastapi.testclient import TestClient

from tests.backend.helpers import find, lecture_with_map, to_tree


def setup(client: TestClient, ctx):  # noqa: ANN001, ANN201
    cid, lid, m = lecture_with_map(client, ctx)
    nid = find(to_tree(m), "Least squares objective")["id"]
    return cid, lid, nid, m, f"/api/courses/{cid}/lectures/{lid}/nodes/{nid}"


def test_test_me_questions_only_from_node_slides(client: TestClient, ctx, fake) -> None:  # noqa: ANN001
    cid, lid, nid, m, base = setup(client, ctx)
    node_slides = {(s["source_id"], s["slide"]) for s in m["nodes"][nid]["sources"]}
    out = client.post(f"{base}/test-me").json()
    qs = out["questions"]
    assert len(qs) == 3
    assert all((q["source"]["source_id"], q["source"]["slide"]) in node_slides for q in qs)
    # the model only saw this node's slides
    prompt = fake.calls[-1]["messages"][1].content
    assert "[Slide 8]" in prompt and "[Slide 4]" not in prompt
    # Test me updates last_studied_at
    m2 = client.get(f"/api/courses/{cid}/lectures/{lid}/map").json()
    assert m2["nodes"][nid]["last_studied_at"]


def test_test_me_rejects_out_of_node_slide(client: TestClient, ctx, fake) -> None:  # noqa: ANN001
    cid, lid, nid, m, base = setup(client, ctx)
    fake.handlers["test_me_generate"] = lambda messages, schema: {"questions": [
        {"question": "From elsewhere?", "slide": 21}, {"question": "Ok?", "slide": 9}]}
    qs = client.post(f"{base}/test-me").json()["questions"]
    node_slides = {s["slide"] for s in m["nodes"][nid]["sources"]}
    assert all(q["source"]["slide"] in node_slides for q in qs)


def test_grade_saved_and_in_history(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, nid, m, base = setup(client, ctx)
    qs = client.post(f"{base}/test-me").json()["questions"]
    items = [
        {"question": qs[0]["question"], "answer": "sum of squared errors over all examples", "source": qs[0]["source"]},
        {"question": qs[1]["question"], "answer": "convex function", "source": qs[1]["source"]},
        {"question": qs[2]["question"], "answer": "", "source": qs[2]["source"]},
    ]
    rec = client.post(f"{base}/test-me/grade", json={"items": items}).json()
    verdicts = [i["verdict"] for i in rec["details"]["items"]]
    assert verdicts == ["correct", "partly", "wrong"]
    assert rec["score"] == 0.5 and rec["kind"] == "test_me"
    assert all("slide" in i["feedback"] for i in rec["details"]["items"])
    hist = client.get(f"{base}/history").json()
    assert [h["id"] for h in hist] == [rec["id"]]
    raw = (ctx.storage.paths.results(cid, lid)).read_text().strip().splitlines()
    assert len(raw) == 1


def test_capture_goes_to_deepest_context_fast(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, nid, m, base = setup(client, ctx)
    t = time.perf_counter()
    r = client.post("/api/notes/capture", json={"text": "remember convexity", "course_id": cid, "lecture_id": lid, "node_id": nid})
    assert time.perf_counter() - t < 1.0
    assert r.json()["where"] == "node"
    assert client.post("/api/notes/capture", json={"text": "lecture note", "course_id": cid, "lecture_id": lid}).json()["where"] == "lecture"
    assert client.post("/api/notes/capture", json={"text": "course note", "course_id": cid}).json()["where"] == "course"
    assert client.post("/api/notes/capture", json={"text": "loose idea"}).json()["where"] == "inbox"
    node_notes = client.get(f"/api/courses/{cid}/lectures/{lid}/notes", params={"node_id": nid}).json()
    assert [n["text"] for n in node_notes] == ["remember convexity"]
    assert len(client.get(f"/api/courses/{cid}/lectures/{lid}/notes").json()) == 2
    assert [n["text"] for n in client.get(f"/api/courses/{cid}/notes").json()] == ["course note"]
    assert [i["text"] for i in client.get("/api/inbox").json()] == ["loose idea"]


def test_note_edit_delete(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, nid, m, base = setup(client, ctx)
    n = client.post(f"/api/courses/{cid}/lectures/{lid}/notes", json={"text": "a", "node_id": nid}).json()
    assert client.patch(f"/api/courses/{cid}/lectures/{lid}/notes/{n['id']}", json={"text": "b"}).json()["text"] == "b"
    assert client.delete(f"/api/courses/{cid}/lectures/{lid}/notes/{n['id']}").status_code == 204
    assert client.delete(f"/api/courses/{cid}/lectures/{lid}/notes/{n['id']}").status_code == 404


def test_inbox_suggest_and_file(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, nid, m, base = setup(client, ctx)
    item = client.post("/api/notes/capture", json={"text": "ridge regression shrinks the weights"}).json()["inbox_item"]
    sug = client.post(f"/api/inbox/{item['id']}/suggest").json()["suggestion"]
    ridge = find(to_tree(m), "Ridge regression")["id"]
    assert sug["node_id"] == ridge and "Ridge regression" in sug["label"]
    res = client.post(f"/api/inbox/{item['id']}/file", json=sug).json()
    assert res["where"] == "node"
    assert client.get("/api/inbox").json() == []
    assert client.get(f"/api/courses/{cid}/lectures/{lid}/notes", params={"node_id": ridge}).json()[0]["text"].startswith("ridge")
    # manual "Change": destinations list includes course, lecture, nodes
    dests = client.get("/api/inbox/destinations").json()
    assert dests[0]["lecture_id"] is None and any(d["node_id"] == nid for d in dests)


def test_partial_grade_not_saved(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, nid, m, base = setup(client, ctx)
    qs = client.post(f"{base}/test-me").json()["questions"]
    item = {"question": qs[0]["question"], "answer": "something here ok", "source": qs[0]["source"]}
    client.post(f"{base}/test-me/grade", json={"items": [item], "save": False})
    assert client.get(f"{base}/history").json() == []


def test_save_finished_test(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, nid, m, base = setup(client, ctx)
    res = [{"question": "q", "answer": "a", "verdict": "correct", "feedback": "ok", "source": None},
           {"question": "q2", "answer": "", "verdict": "wrong", "feedback": "x", "source": None}]
    rec = client.post(f"{base}/test-me/save", json={"results": res}).json()
    assert rec["score"] == 0.5
    assert [h["id"] for h in client.get(f"{base}/history").json()] == [rec["id"]]
