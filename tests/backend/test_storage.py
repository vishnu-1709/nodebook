from __future__ import annotations

import json
import os
import threading
from pathlib import Path

import pytest

from backend.core.ids import is_id, new_id
from backend.core.paths import DataPaths, PathError
from backend.core.schemas import Course, Doc, ResultRecord
from backend.core.storage import MigrationError, MigrationRegistry, Storage


def test_ulid_sortable_and_unique() -> None:
    ids = [new_id() for _ in range(2000)]
    assert len(set(ids)) == 2000
    assert ids == sorted(ids)
    assert all(is_id(i) for i in ids)


def test_paths_reject_escape(tmp_path: Path) -> None:
    p = DataPaths(tmp_path)
    with pytest.raises(PathError):
        p.check(tmp_path / ".." / "evil.json")
    with pytest.raises(PathError):
        p.course("../../etc")
    with pytest.raises(PathError):
        p.source_file(new_id(), new_id(), "p/df")
    assert p.check("courses") == (tmp_path / "courses").resolve()


def test_atomic_write_and_read(tmp_path: Path) -> None:
    st = Storage(tmp_path)
    c = Course(name="Linear Algebra")
    path = st.paths.course(c.id)
    st.write_doc(path, c)
    raw = json.loads(path.read_text())
    assert raw["schema"] == 1 and raw["name"] == "Linear Algebra"
    assert not path.with_name("course.json.tmp").exists()
    assert st.read_doc(path, Course) == c


def test_failed_write_keeps_old_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    st = Storage(tmp_path)
    c = Course(name="A")
    path = st.paths.course(c.id)
    st.write_doc(path, c)

    def boom(*_a: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    c.name = "B"
    with pytest.raises(OSError):
        st.write_doc(path, c)
    monkeypatch.undo()
    assert st.read_doc(path, Course).name == "A"


def test_update_doc_concurrent(tmp_path: Path) -> None:
    st = Storage(tmp_path)
    c = Course(name="x")
    path = st.paths.course(c.id)
    st.write_doc(path, c)

    def worker() -> None:
        for _ in range(25):
            with st.update_doc(path, Course) as doc:
                doc.lecture_order.append(new_id())

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(st.read_doc(path, Course).lecture_order) == 100


def test_jsonl_append_and_torn_line(tmp_path: Path) -> None:
    st = Storage(tmp_path)
    path = st.paths.root / "r.jsonl"
    st.append_jsonl(path, ResultRecord(node_id="n", kind="test_me", score=1.0))
    st.append_jsonl(path, ResultRecord(node_id="n", kind="recall", score=0.5))
    with open(path, "a") as fh:
        fh.write('{"node_id": "n", "ki')  # torn write after crash
    rows = st.read_jsonl(path, ResultRecord)
    assert [r.kind for r in rows] == ["test_me", "recall"]


class _V2(Doc):
    KIND = "demo"
    VERSION = 2
    title: str


def test_migration_upgrades_and_rewrites(tmp_path: Path) -> None:
    reg = MigrationRegistry()

    @reg.register("demo", 1)
    def _v1_to_v2(d: dict) -> dict:
        d["title"] = d.pop("name")
        return d

    st = Storage(tmp_path, migrations=reg)
    path = st.paths.root / "demo.json"
    path.write_text(json.dumps({"schema": 1, "name": "old"}))
    doc = st.read_doc(path, _V2)
    assert doc.title == "old"
    assert json.loads(path.read_text())["schema"] == 2


def test_migration_rejects_newer(tmp_path: Path) -> None:
    st = Storage(tmp_path, migrations=MigrationRegistry())
    path = st.paths.root / "demo.json"
    path.write_text(json.dumps({"schema": 9, "title": "x"}))
    with pytest.raises(MigrationError):
        st.read_doc(path, _V2)


def test_delete_tree_refuses_root(tmp_path: Path) -> None:
    st = Storage(tmp_path)
    with pytest.raises(ValueError):
        st.delete_tree(st.paths.root)
