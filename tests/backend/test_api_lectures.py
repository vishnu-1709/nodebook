from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

DECKS = Path(__file__).resolve().parent.parent / "fixtures" / "decks"


def make_course(client: TestClient) -> str:
    return client.post("/api/courses", json={"name": "ML"}).json()["id"]


def upload(client: TestClient, cid: str, name: str = "linear_regression.pdf") -> dict:
    with open(DECKS / name, "rb") as fh:
        r = client.post(f"/api/courses/{cid}/lectures", files={"file": (name, fh, "application/octet-stream")})
    assert r.status_code == 201, r.text
    return r.json()


def test_upload_pdf_creates_lecture_and_map(client: TestClient, ctx, data_dir: Path) -> None:  # noqa: ANN001
    cid = make_course(client)
    body = upload(client, cid)
    lid, jid = body["lecture"]["id"], body["job"]["id"]
    assert body["lecture"]["title"] == "Linear regression"
    sid = body["lecture"]["source_ids"][0]
    assert (data_dir / "courses" / cid / "sources" / f"{sid}.pdf").exists()

    job = ctx.jobs.wait(jid)
    assert job.state == "done", job.error
    lec = client.get(f"/api/courses/{cid}/lectures/{lid}").json()
    assert lec["map_status"] == "ready"
    assert any(u["slide"] == 2 for u in lec["uncovered_slides"])
    m = client.get(f"/api/courses/{cid}/lectures/{lid}/map").json()
    assert m["schema"] == 1 and m["root_id"] in m["nodes"]
    some = next(n for n in m["nodes"].values() if n["parent_id"])
    assert some["sources"][0]["source_id"] == sid

    slides = client.get(f"/api/courses/{cid}/sources/{sid}/slides").json()
    assert len(slides["slides"]) == 25
    r = client.get(f"/api/courses/{cid}/sources/{sid}/slides/5/thumb")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png"
    detail = client.get(f"/api/courses/{cid}").json()
    assert [l["id"] for l in detail["lectures"]] == [lid]


def test_upload_pptx(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid = make_course(client)
    body = upload(client, cid, "sorting.pptx")
    job = ctx.jobs.wait(body["job"]["id"], timeout=120)
    assert job.state == "done", job.error


def test_upload_rejects_other_types(client: TestClient) -> None:
    cid = make_course(client)
    r = client.post(f"/api/courses/{cid}/lectures", files={"file": ("notes.txt", b"hello", "text/plain")})
    assert r.status_code == 400


def test_map_job_failure_is_reported(client: TestClient, ctx) -> None:  # noqa: ANN001
    from backend.llm.base import LLMError

    def boom(messages, schema):  # noqa: ANN001, ANN202
        raise LLMError("Can't reach Ollama. Is it running?")

    ctx.provider.handlers["map_chunk"] = boom
    cid = make_course(client)
    body = upload(client, cid)
    job = ctx.jobs.wait(body["job"]["id"])
    assert job.state == "failed" and "Ollama" in job.error
    lec = client.get(f"/api/courses/{cid}/lectures/{body['lecture']['id']}").json()
    assert lec["map_status"] == "failed" and "Ollama" in lec["map_error"]

    # retry works once the model is back
    del ctx.provider.handlers["map_chunk"]
    from backend.llm.fake_handlers import map_chunk

    ctx.provider.handlers["map_chunk"] = map_chunk
    job2 = client.post(f"/api/courses/{cid}/lectures/{body['lecture']['id']}/map/generate").json()
    assert ctx.jobs.wait(job2["id"]).state == "done"


def test_reorder_rename_delete_lecture(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid = make_course(client)
    a = upload(client, cid)
    b = upload(client, cid, "sorting.pptx")
    ctx.jobs.wait(a["job"]["id"])
    ctx.jobs.wait(b["job"]["id"], timeout=120)
    la, lb = a["lecture"]["id"], b["lecture"]["id"]
    r = client.put(f"/api/courses/{cid}/lecture-order", json={"order": [lb, la]})
    assert [l["id"] for l in r.json()] == [lb, la]
    assert client.put(f"/api/courses/{cid}/lecture-order", json={"order": [lb]}).status_code == 400
    assert client.patch(f"/api/courses/{cid}/lectures/{la}", json={"title": "Week 1"}).json()["title"] == "Week 1"
    assert client.delete(f"/api/courses/{cid}/lectures/{la}").status_code == 204
    assert [l["id"] for l in client.get(f"/api/courses/{cid}").json()["lectures"]] == [lb]
    # its source stays on the shelf
    srcs = client.get(f"/api/courses/{cid}/sources").json()
    assert len(srcs) == 2


def test_sources_shelf(client: TestClient) -> None:
    cid = make_course(client)
    r = client.post(f"/api/courses/{cid}/sources", files={"file": ("pyq_2023.pdf", open(DECKS / "linear_regression.pdf", "rb"))},
                    data={"kind": "pyq"})
    assert r.status_code == 201 and r.json()["kind"] == "pyq"
    sid = r.json()["id"]
    r = client.post(f"/api/courses/{cid}/sources", files={"file": ("notes.md", b"# Notes\n\nSome text.\n\nMore.")})
    assert r.status_code == 201
    assert len(client.get(f"/api/courses/{cid}/sources/{r.json()['id']}/slides").json()["slides"]) == 1
    assert client.patch(f"/api/courses/{cid}/sources/{sid}", json={"kind": "textbook"}).json()["kind"] == "textbook"
    assert client.delete(f"/api/courses/{cid}/sources/{sid}").status_code == 204
    assert client.post(f"/api/courses/{cid}/sources", files={"file": ("x.exe", b"MZ")}).status_code == 400
