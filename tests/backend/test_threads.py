from __future__ import annotations

import json
from datetime import timedelta

from fastapi.testclient import TestClient

from backend.app import create_app
from backend.core.clock import now
from backend.core.schemas import RecentDoc, RecentExchange, ThreadsDoc
from backend.llm.base import LLMError
from tests.backend.helpers import find, lecture_with_map, to_tree


def ask(client: TestClient, base: str, node_id: str, **body) -> list[dict]:  # noqa: ANN003
    with client.stream("POST", f"{base}/nodes/{node_id}/ask", json=body) as r:
        assert r.status_code == 200, r.read()
        text = "".join(r.iter_text())
    return [json.loads(line[6:]) for line in text.split("\n\n") if line.startswith("data: ")]


def setup(client: TestClient, ctx):  # noqa: ANN001, ANN201
    cid, lid, m = lecture_with_map(client, ctx)
    nid = find(to_tree(m), "Normal equations")["id"]
    return cid, lid, nid, f"/api/courses/{cid}/lectures/{lid}"


def test_ask_streams_and_is_temporary(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, nid, base = setup(client, ctx)
    ev = ask(client, base, nid, content="What are the normal equations?", mode="normal")
    assert ev[0]["type"] == "start" and ev[0]["kept"] is False
    assert any(e["type"] == "delta" for e in ev)
    done = ev[-1]
    assert done["type"] == "done"
    msgs = done["exchange"]["messages"]
    assert [m["kind"] for m in msgs] == ["question", "answer"]
    assert "slide 9" in msgs[1]["content"]
    th = client.get(f"{base}/nodes/{nid}/thread").json()
    assert th["kept"] == [] and len(th["recent"]) == 1


def test_try_first_then_attempt(client: TestClient, ctx, fake) -> None:  # noqa: ANN001
    cid, lid, nid, base = setup(client, ctx)
    ev = ask(client, base, nid, content="Why invert XᵀX?", mode="try_first")
    ex = ev[-1]["exchange"]
    assert ex["messages"][-1]["kind"] == "try_first"
    ev2 = ask(client, base, nid, content="To solve for w", mode="try_first", action="attempt", exchange_id=ex["id"])
    msgs = ev2[-1]["exchange"]["messages"]
    assert [m["kind"] for m in msgs] == ["question", "try_first", "attempt", "answer"]
    # the model saw the whole exchange
    last_call = fake.calls[-1]["messages"]
    assert [m.role for m in last_call] == ["system", "user", "assistant", "user"]
    ev3 = ask(client, base, nid, action="why", exchange_id=ex["id"])
    assert ev3[-1]["exchange"]["messages"][-2]["content"] == "Explain why."


def test_hint_mode_never_answers(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, nid, base = setup(client, ctx)
    ev = ask(client, base, nid, content="What's the solution?", mode="hint")
    assert ev[-1]["exchange"]["messages"][-1]["kind"] == "hint"
    ev2 = ask(client, base, nid, content="w = X y?", mode="hint", action="attempt", exchange_id=ev[-1]["exchange"]["id"])
    assert ev2[-1]["exchange"]["messages"][-1]["kind"] == "hint"


def test_context_has_slides_and_kept_history(client: TestClient, ctx, fake) -> None:  # noqa: ANN001
    cid, lid, nid, base = setup(client, ctx)
    first = ask(client, base, nid, content="First kept question", mode="normal")[-1]["exchange"]
    client.post(f"{base}/exchanges/{first['id']}/keep")
    ask(client, base, nid, content="Second one", mode="normal")
    system = fake.calls[-1]["messages"][0].content
    assert "Normal equations" in system and "Xᵀ(Xw − y) = 0" in system
    assert "First kept question" in system
    assert "only from the provided slides" in system


def test_keep_unkeep_undo_and_counts(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, nid, base = setup(client, ctx)
    ex = ask(client, base, nid, content="Q?", mode="normal")[-1]["exchange"]
    assert client.post(f"{base}/exchanges/{ex['id']}/keep").json()["kept_at"]
    assert client.get(f"{base}/threads/counts").json() == {nid: 1}
    th = client.get(f"{base}/nodes/{nid}/thread").json()
    assert len(th["kept"]) == 1 and th["recent"] == []
    client.post(f"{base}/exchanges/{ex['id']}/unkeep")
    assert client.get(f"{base}/threads/counts").json() == {}
    client.post(f"{base}/exchanges/{ex['id']}/keep")  # undo within 5 s
    th = client.get(f"{base}/nodes/{nid}/thread").json()
    assert [e["id"] for e in th["kept"]] == [ex["id"]]
    assert len(th["kept"][0]["messages"]) == 2


def test_keep_all_setting(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, nid, base = setup(client, ctx)
    client.patch("/api/settings", json={"keep_all_questions": True})
    ev = ask(client, base, nid, content="Q?", mode="normal")
    assert ev[0]["kept"] is True
    assert len(client.get(f"{base}/nodes/{nid}/thread").json()["kept"]) == 1


def test_expired_doubts_gone_on_next_launch(client: TestClient, ctx, settings_store, fake, tmp_path) -> None:  # noqa: ANN001
    cid, lid, nid, base = setup(client, ctx)
    ex = ask(client, base, nid, content="Old doubt", mode="normal")[-1]["exchange"]
    kept = ask(client, base, nid, content="Kept forever", mode="normal")[-1]["exchange"]
    client.post(f"{base}/exchanges/{kept['id']}/keep")
    st = ctx.storage
    with st.update_doc(st.paths.recent(cid, lid), RecentDoc) as doc:
        for r in doc.items:
            r.expires_at = (now() - timedelta(minutes=1)).isoformat()
        doc.items.append(RecentExchange(node_id=nid, expires_at=(now() + timedelta(days=1)).isoformat()))
    with st.update_doc(st.paths.threads(cid, lid), ThreadsDoc) as th:  # kept ones never expire
        th.by_node[nid][0].kept_at = (now() - timedelta(days=400)).isoformat()
    app2 = create_app(settings_store=settings_store, provider=fake, static_dir=tmp_path / "none")
    with TestClient(app2):
        pass  # startup purge
    raw = st.read_doc(st.paths.recent(cid, lid), RecentDoc)
    assert ex["id"] not in [r.id for r in raw.items] and len(raw.items) == 1
    assert len(st.read_doc(st.paths.threads(cid, lid), ThreadsDoc).by_node[nid]) == 1


def test_llm_error_event(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, nid, base = setup(client, ctx)

    def boom(messages, schema):  # noqa: ANN001, ANN202
        raise LLMError("Can't reach Ollama. Is it running?")

    ctx.provider.handlers["node_answer"] = boom
    ev = ask(client, base, nid, content="Q?", mode="normal")
    assert ev[-1] == {"type": "error", "message": "Can't reach Ollama. Is it running?"}
    th = client.get(f"{base}/nodes/{nid}/thread").json()
    assert all(not r["messages"] for r in th["recent"])


def test_from_kept_exchange(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, nid, base = setup(client, ctx)
    ex = ask(client, base, nid, content="What does XᵀX need to be?", mode="normal")[-1]["exchange"]
    client.post(f"{base}/exchanges/{ex['id']}/keep")
    card = client.post(f"{base}/exchanges/{ex['id']}/to-card").json()
    assert card["front"] == "What does XᵀX need to be?" and card["node_id"] == nid and card["origin"]["kind"] == "thread"
    note = client.post(f"{base}/exchanges/{ex['id']}/to-note").json()
    assert note["node_id"] == nid and note["pinned_from"] == ex["id"]
    m = client.post(f"{base}/exchanges/{ex['id']}/to-node").json()
    kids = [m["nodes"][c]["label"] for c in m["nodes"][nid]["children"]]
    assert kids == ["What does XᵀX need to be"]
