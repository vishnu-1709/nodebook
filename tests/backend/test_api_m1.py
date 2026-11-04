from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.core.jobs import JobManager


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_course_crud_persists(client: TestClient, app, settings_store, fake, tmp_path: Path) -> None:  # noqa: ANN001
    r = client.post("/api/courses", json={"name": "Signals & Systems"})
    assert r.status_code == 201
    cid = r.json()["id"]
    assert [c["name"] for c in client.get("/api/courses").json()] == ["Signals & Systems"]

    r = client.patch(f"/api/courses/{cid}", json={"name": "Signals"})
    assert r.json()["name"] == "Signals"

    # a fresh app over the same settings sees the course (persisted on disk)
    app2 = create_app(settings_store=settings_store, provider=fake, static_dir=tmp_path / "none")
    with TestClient(app2) as c2:
        detail = c2.get(f"/api/courses/{cid}").json()
        assert detail["course"]["name"] == "Signals"
        assert detail["lectures"] == []

    assert client.delete(f"/api/courses/{cid}").status_code == 204
    assert client.get(f"/api/courses/{cid}").status_code == 404


def test_course_bad_id(client: TestClient) -> None:
    assert client.get("/api/courses/..%2F..").status_code in (400, 404)
    assert client.get("/api/courses/not-an-id").status_code == 400


def test_course_name_required(client: TestClient) -> None:
    assert client.post("/api/courses", json={"name": ""}).status_code == 422


def test_settings_roundtrip(client: TestClient, tmp_path: Path) -> None:
    s = client.get("/api/settings").json()
    assert s["theme"] == "system"
    new_dir = tmp_path / "elsewhere"
    r = client.patch("/api/settings", json={"theme": "dark", "data_dir": str(new_dir)})
    assert r.status_code == 200
    assert r.json()["theme"] == "dark"
    assert new_dir.is_dir()
    client.post("/api/courses", json={"name": "In new folder"})
    assert (new_dir / "courses").is_dir()


def test_settings_rejects_relative(client: TestClient) -> None:
    assert client.patch("/api/settings", json={"data_dir": "rel/path"}).status_code == 400
    assert client.patch("/api/settings", json={"bogus": 1}).status_code == 422


def test_ollama_status_fake(client: TestClient) -> None:
    body = client.get("/api/ollama/status").json()
    assert body["status"]["reachable"] is True
    assert any(m["vision"] for m in body["models"])


def test_ollama_status_down(tmp_path: Path, settings_store) -> None:  # noqa: ANN001
    from backend.llm.ollama import OllamaProvider

    app = create_app(settings_store=settings_store, provider=OllamaProvider("http://127.0.0.1:9"),
                     static_dir=tmp_path / "none")
    with TestClient(app) as c:
        body = c.get("/api/ollama/status").json()
        assert body["status"]["reachable"] is False
        assert "Ollama" in body["status"]["error"]


def test_jobs_progress_and_failure() -> None:
    jm = JobManager()

    def ok(ctx):  # noqa: ANN001, ANN202
        ctx.report("step", 0.5)
        return {"x": 1}

    def bad(ctx):  # noqa: ANN001, ANN202
        raise RuntimeError("nope")

    a = jm.wait(jm.submit("t", ok).id)
    b = jm.wait(jm.submit("t", bad).id)
    assert a and a.state == "done" and a.result == {"x": 1}
    assert b and b.state == "failed" and b.error == "nope"
    jm.shutdown()


def test_spa_served(tmp_path: Path, settings_store, fake) -> None:  # noqa: ANN001
    sdir = tmp_path / "static"
    (sdir / "assets").mkdir(parents=True)
    (sdir / "index.html").write_text("<html>nodebook</html>")
    (sdir / "assets" / "a.js").write_text("console.log(1)")
    app = create_app(settings_store=settings_store, provider=fake, static_dir=sdir)
    with TestClient(app) as c:
        assert "nodebook" in c.get("/").text
        assert "nodebook" in c.get("/course/123").text
        assert c.get("/assets/a.js").status_code == 200
        assert c.get("/api/nope").status_code == 404
