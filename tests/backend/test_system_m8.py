from __future__ import annotations

import io
import json
import zipfile

from fastapi.testclient import TestClient

from backend.api.system import load_recommendations
from tests.backend.helpers import DECKS, lecture_with_map


def test_system_and_recommendations(client: TestClient) -> None:
    s = client.get("/api/system").json()
    assert s["ram_gb"] > 0 and s["version"]
    r = client.get("/api/models/recommended").json()
    assert r["map"] and r["study"] and r["tier_label"]
    assert all("installed" in m for m in r["map"])


def test_recommendations_file_shape() -> None:
    data = load_recommendations()
    tiers = data["tiers"]
    assert tiers[0]["min_ram_gb"] == 0
    assert all(t["map"] and t["study"] for t in tiers)
    assert any(m.get("vision") for t in tiers for m in t["map"])


def test_pull_job_reports_progress(client: TestClient, ctx, fake) -> None:  # noqa: ANN001
    job = client.post("/api/ollama/pull", json={"name": "qwen2.5:7b"}).json()
    done = ctx.jobs.wait(job["id"])
    assert done.state == "done" and done.progress == 1.0
    assert "qwen2.5:7b" in fake.pulled
    assert any(m["name"] == "qwen2.5:7b" for m in client.get("/api/ollama/status").json()["models"])


def test_test_on_my_slides(client: TestClient, ctx, data_dir) -> None:  # noqa: ANN001
    with open(DECKS / "linear_regression.pdf", "rb") as fh:
        job = client.post("/api/ollama/test-map", files={"file": ("linear_regression.pdf", fh)}).json()
    done = ctx.jobs.wait(job["id"])
    assert done.state == "done", done.error
    assert done.result["outline"][0] == "linear_regression" and done.result["nodes"] > 5
    assert not (data_dir / "courses").exists()  # nothing saved


def test_export_import_roundtrip(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, m = lecture_with_map(client, ctx)
    client.post(f"/api/courses/{cid}/notes", json={"text": "keep me"})
    r = client.get(f"/api/courses/{cid}/export")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    z = zipfile.ZipFile(io.BytesIO(r.content))
    assert json.loads(z.read("nodebook-course.json"))["course_id"] == cid
    # importing next to the original gets a new id and rewritten references
    new = client.post("/api/courses/import", files={"file": ("c.zip", r.content)}).json()["course_id"]
    assert new != cid
    detail = client.get(f"/api/courses/{new}").json()
    assert detail["course"]["id"] == new and detail["lectures"][0]["course_id"] == new
    assert client.get(f"/api/courses/{new}/lectures/{lid}/map").status_code == 200
    assert client.get(f"/api/courses/{new}/notes").json()[0]["text"] == "keep me"


def test_import_rejects_bad_zips(client: TestClient) -> None:
    assert client.post("/api/courses/import", files={"file": ("x.zip", b"nope")}).status_code == 400
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("nodebook-course.json", json.dumps({"course_id": "01JAAAAAAAAAAAAAAAAAAAAAAA"}))
        z.writestr("course/../../evil.json", "{}")
    assert client.post("/api/courses/import", files={"file": ("x.zip", buf.getvalue())}).status_code == 400
