from __future__ import annotations

from fastapi.testclient import TestClient

from backend.core.ids import new_id
from backend.core.schemas import Exchange, Message, PracticeDoc, PracticeItem, ThreadsDoc
from tests.backend.helpers import detach, find, lecture_with_map, to_tree


def attach_data(ctx, cid: str, lid: str, node_id: str) -> None:  # noqa: ANN001
    st = ctx.storage
    st.write_doc(st.paths.threads(cid, lid), ThreadsDoc(by_node={node_id: [Exchange(
        kept_at="2026-01-01T00:00:00+00:00",
        messages=[Message(role="user", kind="question", content="why?")])]}))
    st.write_doc(st.paths.practice(cid, lid), PracticeDoc(items=[PracticeItem(type="card", node_id=node_id, front="Q", back="A")]))


def attached(ctx, cid: str, lid: str) -> tuple[list[str], list[str | None]]:  # noqa: ANN001
    st = ctx.storage
    th = st.read_doc(st.paths.threads(cid, lid), ThreadsDoc)
    pr = st.read_doc(st.paths.practice(cid, lid), PracticeDoc)
    return [k for k, v in th.by_node.items() if v], [i.node_id for i in pr.items]


def test_rename_and_move_keep_threads_and_cards(client: TestClient, ctx) -> None:  # noqa: ANN001
    """AC 5.3: rename/move a node → its thread and cards still attached after reload."""
    cid, lid, m = lecture_with_map(client, ctx)
    tree = to_tree(m)
    target = find(tree, "Normal equations")
    nid = target["id"]
    sources_before = m["nodes"][nid]["sources"]
    attach_data(ctx, cid, lid, nid)

    # rename + move under the root, via the structure sync used by the editor
    moved = detach(tree, nid)
    moved["label"] = "Closed-form solution"
    tree["children"].append(moved)
    r = client.put(f"/api/courses/{cid}/lectures/{lid}/map/structure", json=tree)
    assert r.status_code == 200, r.text

    m2 = client.get(f"/api/courses/{cid}/lectures/{lid}/map").json()  # "reload"
    n = m2["nodes"][nid]
    assert n["label"] == "Closed-form solution"
    assert n["parent_id"] == m2["root_id"]
    assert n["sources"] == sources_before
    threads, cards = attached(ctx, cid, lid)
    assert threads == [nid] and cards == [nid]


def test_delete_rehomes_to_parent(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, m = lecture_with_map(client, ctx)
    tree = to_tree(m)
    parent = find(tree, "Least squares objective")
    child = find(tree, "Normal equations")
    attach_data(ctx, cid, lid, child["id"])
    detach(tree, child["id"])
    assert client.put(f"/api/courses/{cid}/lectures/{lid}/map/structure", json=tree).status_code == 200
    m2 = client.get(f"/api/courses/{cid}/lectures/{lid}/map").json()
    assert child["id"] not in m2["nodes"]
    threads, cards = attached(ctx, cid, lid)
    assert threads == [parent["id"]] and cards == [parent["id"]]


def test_structure_add_new_nodes_and_collapse(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, m = lecture_with_map(client, ctx)
    tree = to_tree(m)
    nid = new_id()
    tree["children"][0]["children"].append({"id": nid, "label": "My own node", "collapsed": False, "children": []})
    tree["children"][1]["collapsed"] = True
    r = client.put(f"/api/courses/{cid}/lectures/{lid}/map/structure", json=tree)
    assert r.status_code == 200
    m2 = r.json()
    assert m2["nodes"][nid]["origin"] == "user"
    assert m2["nodes"][nid]["parent_id"] == tree["children"][0]["id"]
    assert m2["nodes"][tree["children"][1]["id"]]["collapsed"] is True


def test_structure_rejects_bad_input(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, m = lecture_with_map(client, ctx)
    url = f"/api/courses/{cid}/lectures/{lid}/map/structure"
    tree = to_tree(m)
    tree["children"].append({"id": "me-generated-123", "label": "x", "children": []})
    assert client.put(url, json=tree).status_code == 400
    tree = to_tree(m)
    tree["children"].append(dict(tree["children"][0]))
    assert client.put(url, json=tree).status_code == 400
    tree = to_tree(m)
    tree["id"] = new_id()
    assert client.put(url, json=tree).status_code == 400
    tree = to_tree(m)
    tree["children"][0]["label"] = "   "
    assert client.put(url, json=tree).status_code == 400


def test_status_and_studied(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, m = lecture_with_map(client, ctx)
    nid = m["root_id"]
    nid = m["nodes"][nid]["children"][0]
    r = client.patch(f"/api/courses/{cid}/lectures/{lid}/map/nodes/{nid}", json={"status": "confused", "studied": True})
    n = r.json()["nodes"][nid]
    assert n["status"] == "confused" and n["status_mode"] == "manual" and n["last_studied_at"]


def test_ai_expand_preview_then_apply(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, m = lecture_with_map(client, ctx)
    nid = find(to_tree(m), "Normal equations")["id"]
    base = f"/api/courses/{cid}/lectures/{lid}/map"
    p = client.post(f"{base}/nodes/{nid}/suggest", json={"action": "expand"}).json()
    assert p["action"] == "expand" and len(p["parts"]) >= 2
    assert all(part["sources"] for part in p["parts"])
    # preview didn't change anything
    assert client.get(base).json()["nodes"][nid]["children"] == []
    p["parts"][0]["label"] = "Edited by me"
    m2 = client.post(f"{base}/apply", json=p).json()
    kids = [m2["nodes"][c]["label"] for c in m2["nodes"][nid]["children"]]
    assert kids[0] == "Edited by me" and len(kids) == len(p["parts"])


def test_ai_split_keeps_id(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, m = lecture_with_map(client, ctx)
    node = find(to_tree(m), "The linear model")
    nid = node["id"]
    attach_data(ctx, cid, lid, nid)
    base = f"/api/courses/{cid}/lectures/{lid}/map"
    p = client.post(f"{base}/nodes/{nid}/suggest", json={"action": "split"}).json()
    assert len(p["parts"]) == 2
    m2 = client.post(f"{base}/apply", json=p).json()
    parent = m2["nodes"][m2["nodes"][nid]["parent_id"]]
    idx = parent["children"].index(nid)
    assert m2["nodes"][parent["children"][idx + 1]]["label"] == p["parts"][1]["label"]
    assert attached(ctx, cid, lid)[0] == [nid]


def test_ai_merge_rehomes_sibling(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, m = lecture_with_map(client, ctx)
    tree = to_tree(m)
    a, b = tree["children"][0], tree["children"][1]
    attach_data(ctx, cid, lid, b["id"])
    base = f"/api/courses/{cid}/lectures/{lid}/map"
    p = client.post(f"{base}/nodes/{a['id']}/suggest", json={"action": "merge", "sibling_id": b["id"]}).json()
    assert p["label"]
    m2 = client.post(f"{base}/apply", json=p).json()
    assert b["id"] not in m2["nodes"]
    keep = m2["nodes"][a["id"]]
    assert {(s["slide"]) for s in m["nodes"][b["id"]]["sources"]} <= {s["slide"] for s in keep["sources"]}
    assert attached(ctx, cid, lid) == ([a["id"]], [a["id"]])
    # merging non-siblings is refused
    deep = tree["children"][2]["children"][0]["id"]
    r = client.post(f"{base}/nodes/{a['id']}/suggest", json={"action": "merge", "sibling_id": deep})
    assert r.status_code == 400


def test_ai_simplify(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, m = lecture_with_map(client, ctx)
    nid = find(to_tree(m), "Least squares objective")["id"]
    base = f"/api/courses/{cid}/lectures/{lid}/map"
    p = client.post(f"{base}/nodes/{nid}/suggest", json={"action": "simplify"}).json()
    assert p["label"] and len(p["label"].split()) <= 6
    assert client.post(f"{base}/apply", json=p).json()["nodes"][nid]["label"] == p["label"]


def test_add_uncovered_slides(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, m = lecture_with_map(client, ctx)
    lec = client.get(f"/api/courses/{cid}/lectures/{lid}").json()
    assert lec["uncovered_slides"]
    m2 = client.post(f"/api/courses/{cid}/lectures/{lid}/map/add-uncovered").json()
    labels = {n["label"] for n in m2["nodes"].values()}
    assert "Outline" in labels
    assert client.get(f"/api/courses/{cid}/lectures/{lid}").json()["uncovered_slides"] == []
