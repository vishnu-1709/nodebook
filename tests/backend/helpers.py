from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

DECKS = Path(__file__).resolve().parent.parent / "fixtures" / "decks"


def make_course(client: TestClient, name: str = "ML") -> str:
    return client.post("/api/courses", json={"name": name}).json()["id"]


def lecture_with_map(client: TestClient, ctx: Any, deck: str = "linear_regression.pdf") -> tuple[str, str, dict]:
    cid = make_course(client)
    with open(DECKS / deck, "rb") as fh:
        body = client.post(f"/api/courses/{cid}/lectures", files={"file": (deck, fh)}).json()
    job = ctx.jobs.wait(body["job"]["id"], timeout=120)
    assert job.state == "done", job.error
    lid = body["lecture"]["id"]
    m = client.get(f"/api/courses/{cid}/lectures/{lid}/map").json()
    return cid, lid, m


def to_tree(m: dict, nid: str | None = None) -> dict:
    nid = nid or m["root_id"]
    n = m["nodes"][nid]
    return {"id": nid, "label": n["label"], "collapsed": n["collapsed"],
            "children": [to_tree(m, c) for c in n["children"]]}


def find(tree: dict, label: str) -> dict:
    if tree["label"] == label:
        return tree
    for c in tree["children"]:
        r = find(c, label)
        if r:
            return r
    return {}


def detach(tree: dict, nid: str) -> dict | None:
    for i, c in enumerate(tree["children"]):
        if c["id"] == nid:
            return tree["children"].pop(i)
        r = detach(c, nid)
        if r:
            return r
    return None
