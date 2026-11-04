from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from backend.api.deps import get_ctx
from backend.core.context import AppContext
from backend.core.jobs import JobInfo

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}")
def get_job(job_id: str, ctx: AppContext = Depends(get_ctx)) -> JobInfo:
    job = ctx.jobs.get(job_id)
    if job is None:
        raise HTTPException(404, "job not found")
    return job
