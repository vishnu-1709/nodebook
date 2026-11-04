"""In-process background jobs (map generation, model pulls). The UI polls
``GET /api/jobs/{id}``."""

from __future__ import annotations

import threading
import traceback
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.core.clock import now_iso
from backend.core.ids import new_id

JobState = Literal["queued", "running", "done", "failed"]


class JobInfo(BaseModel):
    id: str = Field(default_factory=new_id)
    kind: str
    state: JobState = "queued"
    step: str = ""
    progress: float = 0.0  # 0..1
    message: str = ""
    error: str | None = None
    result: dict[str, Any] | None = None
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class JobContext:
    """Handed to the job function so it can report progress."""

    def __init__(self, manager: JobManager, job_id: str) -> None:
        self._m = manager
        self.job_id = job_id

    def report(self, step: str, progress: float, message: str = "") -> None:
        self._m._update(self.job_id, step=step, progress=max(0.0, min(1.0, progress)), message=message)


JobFn = Callable[[JobContext], dict[str, Any] | None]


class JobManager:
    def __init__(self, workers: int = 2, max_kept: int = 200) -> None:
        self._jobs: dict[str, JobInfo] = {}
        self._lock = threading.Lock()
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="nodebook-job")
        self._max_kept = max_kept

    def submit(self, kind: str, fn: JobFn, on_error: Callable[[str], None] | None = None) -> JobInfo:
        info = JobInfo(kind=kind)
        with self._lock:
            self._jobs[info.id] = info
            self._trim()
        self._pool.submit(self._run, info.id, fn, on_error)
        return info.model_copy()

    def get(self, job_id: str) -> JobInfo | None:
        with self._lock:
            j = self._jobs.get(job_id)
            return j.model_copy() if j else None

    def wait(self, job_id: str, timeout: float = 30.0) -> JobInfo | None:
        """Test helper: block until a job finishes."""
        import time

        end = time.monotonic() + timeout
        while time.monotonic() < end:
            j = self.get(job_id)
            if j and j.state in ("done", "failed"):
                return j
            time.sleep(0.02)
        return self.get(job_id)

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)

    # -- internals -------------------------------------------------------------
    def _update(self, job_id: str, **fields: Any) -> None:
        with self._lock:
            j = self._jobs.get(job_id)
            if j is None:
                return
            for k, v in fields.items():
                setattr(j, k, v)
            j.updated_at = now_iso()

    def _run(self, job_id: str, fn: JobFn, on_error: Callable[[str], None] | None) -> None:
        self._update(job_id, state="running")
        try:
            result = fn(JobContext(self, job_id))
            self._update(job_id, state="done", progress=1.0, result=result or {})
        except Exception as exc:  # noqa: BLE001 - surface every failure to the UI
            msg = str(exc) or exc.__class__.__name__
            traceback.print_exc()
            self._update(job_id, state="failed", error=msg)
            if on_error:
                try:
                    on_error(msg)
                except Exception:  # noqa: BLE001
                    traceback.print_exc()

    def _trim(self) -> None:
        if len(self._jobs) <= self._max_kept:
            return
        finished = [j for j in self._jobs.values() if j.state in ("done", "failed")]
        finished.sort(key=lambda j: j.updated_at)
        for j in finished[: len(self._jobs) - self._max_kept]:
            del self._jobs[j.id]
