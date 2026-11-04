"""All file I/O for the data folder (SPEC §3 rules).

- Atomic writes: write ``*.tmp`` then ``os.replace``.
- One in-process lock per file.
- Every JSON doc has ``"schema": <int>``; older versions are upgraded through
  the migration registry on read.
"""

from __future__ import annotations

import json
import os
import shutil
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any, BinaryIO, TypeVar

from pydantic import BaseModel

from backend.core.paths import DataPaths
from backend.core.schemas import Doc

D = TypeVar("D", bound=Doc)
M = TypeVar("M", bound=BaseModel)

Migration = Callable[[dict[str, Any]], dict[str, Any]]


class MigrationError(RuntimeError):
    pass


class MigrationRegistry:
    """Maps (kind, from_version) → function returning the doc at from_version + 1."""

    def __init__(self) -> None:
        self._steps: dict[tuple[str, int], Migration] = {}

    def register(self, kind: str, from_version: int) -> Callable[[Migration], Migration]:
        def deco(fn: Migration) -> Migration:
            self._steps[(kind, from_version)] = fn
            return fn

        return deco

    def upgrade(self, kind: str, data: dict[str, Any], target: int) -> tuple[dict[str, Any], bool]:
        version = int(data.get("schema", 1))
        if version > target:
            raise MigrationError(
                f"{kind} file has schema {version}, newer than this app ({target}). Update Nodebook."
            )
        changed = False
        while version < target:
            step = self._steps.get((kind, version))
            if step is None:
                raise MigrationError(f"no migration for {kind} from schema {version}")
            data = step(dict(data))
            version += 1
            data["schema"] = version
            changed = True
        return data, changed


class Storage:
    def __init__(self, root: Path | str, migrations: MigrationRegistry | None = None) -> None:
        self.paths = DataPaths(root)
        self.migrations = migrations or default_migrations
        self._locks: dict[Path, threading.RLock] = {}
        self._locks_guard = threading.Lock()

    # -- locking ---------------------------------------------------------------
    def lock(self, path: Path) -> threading.RLock:
        path = self.paths.check(path)
        with self._locks_guard:
            lk = self._locks.get(path)
            if lk is None:
                lk = threading.RLock()
                self._locks[path] = lk
            return lk

    # -- raw -------------------------------------------------------------------
    def ensure_root(self) -> None:
        self.paths.root.mkdir(parents=True, exist_ok=True)

    def exists(self, path: Path) -> bool:
        return self.paths.check(path).exists()

    def write_bytes_atomic(self, path: Path, data: bytes) -> None:
        path = self.paths.check(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with self.lock(path):
            with open(tmp, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, path)

    def read_bytes(self, path: Path) -> bytes:
        return self.paths.check(path).read_bytes()

    def write_stream(self, path: Path, stream: BinaryIO, max_bytes: int | None = None) -> int:
        """Copy a stream into the data folder atomically. Returns bytes written."""
        path = self.paths.check(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        total = 0
        with self.lock(path):
            try:
                with open(tmp, "wb") as fh:
                    while True:
                        chunk = stream.read(1024 * 1024)
                        if not chunk:
                            break
                        total += len(chunk)
                        if max_bytes is not None and total > max_bytes:
                            raise ValueError("file too large")
                        fh.write(chunk)
                    fh.flush()
                    os.fsync(fh.fileno())
                os.replace(tmp, path)
            except BaseException:
                tmp.unlink(missing_ok=True)
                raise
        return total

    def delete_file(self, path: Path) -> None:
        path = self.paths.check(path)
        with self.lock(path):
            path.unlink(missing_ok=True)

    def delete_tree(self, path: Path) -> None:
        path = self.paths.check(path)
        if path == self.paths.root:
            raise ValueError("refusing to delete the data folder")
        if path.exists():
            shutil.rmtree(path)

    def list_dirs(self, path: Path) -> list[str]:
        path = self.paths.check(path)
        if not path.is_dir():
            return []
        return sorted(p.name for p in path.iterdir() if p.is_dir())

    # -- JSON docs -------------------------------------------------------------
    def read_doc(self, path: Path, model: type[D], default: Callable[[], D] | None = None) -> D:
        path = self.paths.check(path)
        with self.lock(path):
            if not path.exists():
                if default is None:
                    raise FileNotFoundError(path)
                return default()
            data = json.loads(path.read_text("utf-8"))
            data, changed = self.migrations.upgrade(model.KIND, data, model.VERSION)
            doc = model.model_validate(data)
            if changed:
                self.write_doc(path, doc)
            return doc

    def write_doc(self, path: Path, doc: Doc) -> None:
        payload = doc.model_dump(mode="json", by_alias=True)
        payload["schema"] = type(doc).VERSION
        text = json.dumps(payload, ensure_ascii=False, indent=2)
        self.write_bytes_atomic(path, text.encode("utf-8"))

    @contextmanager
    def update_doc(
        self, path: Path, model: type[D], default: Callable[[], D] | None = None
    ) -> Iterator[D]:
        """Read-modify-write under the file lock. Writes only if the block succeeds."""
        path = self.paths.check(path)
        with self.lock(path):
            doc = self.read_doc(path, model, default)
            yield doc
            self.write_doc(path, doc)

    # -- JSONL -----------------------------------------------------------------
    def append_jsonl(self, path: Path, record: BaseModel | dict[str, Any]) -> None:
        path = self.paths.check(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(record, BaseModel):
            data = record.model_dump(mode="json", by_alias=True)
        else:
            data = record
        line = json.dumps(data, ensure_ascii=False) + "\n"
        with self.lock(path):
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line)
                fh.flush()
                os.fsync(fh.fileno())

    def read_jsonl(self, path: Path, model: type[M]) -> list[M]:
        path = self.paths.check(path)
        out: list[M] = []
        with self.lock(path):
            if not path.exists():
                return out
            for raw in path.read_text("utf-8").splitlines():
                raw = raw.strip()
                if not raw:
                    continue
                try:
                    out.append(model.model_validate(json.loads(raw)))
                except (ValueError, json.JSONDecodeError):
                    # A torn last line after a crash must not break reading.
                    continue
        return out


default_migrations = MigrationRegistry()
