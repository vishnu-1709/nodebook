from __future__ import annotations

from fastapi.testclient import TestClient

from backend.pipeline.recall import similarity
from tests.backend.helpers import find, lecture_with_map, to_tree


def test_similarity() -> None:
    assert similarity("Least squares objective", "least-squares objective") == 1.0
    assert similarity("Gradient descent", "Gradiant descent") > 0.86
    assert similarity("Ridge regression", "Overfitting") < 0.5


def test_blank_map_recall_fuzzy_then_llm(client: TestClient, ctx, fake) -> None:  # noqa: ANN001
    cid, lid, m = lecture_with_map(client, ctx)
    t = to_tree(m)
    ids = {lbl: find(t, lbl)["id"] for lbl in ["Gradient descent", "Ridge regression", "Lasso regression", "Feature scaling", "Overfitting"]}
    answers = [
        {"node_id": ids["Gradient descent"], "typed": "gradiant descent"},  # fuzzy
        {"node_id": ids["Ridge regression"], "typed": "L2"},  # synonym → model
        {"node_id": ids["Lasso regression"], "typed": "lasso"},  # near miss → model
        {"node_id": ids["Feature scaling"], "typed": "momentum"},  # wrong
        {"node_id": ids["Overfitting"], "typed": ""},  # blank
    ]
    r = client.post(f"/api/courses/{cid}/lectures/{lid}/recall/judge", json={"answers": answers}).json()
    how = {v["expected"]: (v["correct"], v["how"]) for v in r["verdicts"]}
    assert how["Gradient descent"] == (True, "fuzzy")
    assert how["Ridge regression"] == (True, "judged")
    assert how["Lasso regression"] == (True, "judged")
    assert how["Feature scaling"] == (False, "wrong")
    assert how["Overfitting"] == (False, "blank")
    assert r["correct"] == 3 and r["total"] == 5
    # the fuzzy + blank ones never went to the model
    judged = fake.calls[-1]["messages"][-1].content
    assert "gradiant" not in judged and "Overfitting" not in judged
    # results.jsonl: one record per node
    hist = client.get(f"/api/courses/{cid}/lectures/{lid}/nodes/{ids['Ridge regression']}/history").json()
    assert hist[0]["kind"] == "recall" and hist[0]["score"] == 1.0


def test_explain_it_back(client: TestClient, ctx) -> None:  # noqa: ANN001
    cid, lid, m = lecture_with_map(client, ctx)
    nid = find(to_tree(m), "Normal equations")["id"]
    r = client.post(f"/api/courses/{cid}/lectures/{lid}/nodes/{nid}/explain-back",
                    json={"text": "You set the gradient to zero and the solution requires inverting XᵀX."}).json()
    rv = r["review"]
    assert rv["covered"] and 0 < rv["score"] <= 1
    assert all(p["source"]["slide"] == 9 for p in rv["missing"])
    assert r["record"]["kind"] == "explain"
    hist = client.get(f"/api/courses/{cid}/lectures/{lid}/nodes/{nid}/history").json()
    assert hist[0]["kind"] == "explain"
