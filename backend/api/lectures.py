from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from backend.api.deps import get_ctx
from backend.core import courses as svc
from backend.core.context import AppContext
from backend.core.jobs import JobInfo
from backend.core.schemas import Lecture, MapDoc, SlidesDoc, SourceKind, SourceMeta
from backend.core.usage import log_usage
from backend.pipeline.extract import ParseError, extract_source
from backend.pipeline.lecture_job import start_map_job

router = APIRouter(prefix="/courses/{course_id}", tags=["lectures"])


class LectureCreated(BaseModel):
    lecture: Lecture
    job: JobInfo


class LecturePatch(BaseModel):
    title: str = Field(min_length=1, max_length=200)


class OrderIn(BaseModel):
    order: list[str]


class SourcePatch(BaseModel):
    kind: SourceKind


def _bad(exc: Exception) -> HTTPException:
    return HTTPException(400, str(exc))


# --------------------------------------------------------------------------- lectures

@router.post("/lectures", status_code=201)
def create_lecture(
    course_id: str,
    file: UploadFile = File(...),
    title: str = Form(""),
    ctx: AppContext = Depends(get_ctx),
) -> LectureCreated:
    st = ctx.storage
    filename = file.filename or "slides.pdf"
    if svc.file_ext(filename) not in svc.LECTURE_EXT:
        raise HTTPException(400, "Lectures need a PDF or PPTX file.")
    try:
        meta = svc.add_source(st, course_id, filename, file.file, kind="slides")
    except svc.BadUpload as exc:
        raise _bad(exc) from exc
    lec = svc.create_lecture(st, course_id, title or svc.lecture_title_from_filename(filename), [meta.id])
    svc.update_source(st, course_id, meta.id, lecture_id=lec.id)
    log_usage(ctx, "lecture.create")
    job = start_map_job(ctx, course_id, lec.id)
    return LectureCreated(lecture=svc.get_lecture(st, course_id, lec.id), job=job)


@router.get("/lectures/{lecture_id}")
def get_lecture(course_id: str, lecture_id: str, ctx: AppContext = Depends(get_ctx)) -> Lecture:
    return svc.get_lecture(ctx.storage, course_id, lecture_id)


@router.patch("/lectures/{lecture_id}")
def rename_lecture(course_id: str, lecture_id: str, body: LecturePatch, ctx: AppContext = Depends(get_ctx)) -> Lecture:
    return svc.update_lecture(ctx.storage, course_id, lecture_id, title=body.title.strip())


@router.delete("/lectures/{lecture_id}", status_code=204)
def delete_lecture(course_id: str, lecture_id: str, ctx: AppContext = Depends(get_ctx)) -> None:
    svc.delete_lecture(ctx.storage, course_id, lecture_id)


@router.put("/lecture-order")
def reorder(course_id: str, body: OrderIn, ctx: AppContext = Depends(get_ctx)) -> list[Lecture]:
    try:
        return svc.reorder_lectures(ctx.storage, course_id, body.order)
    except svc.BadUpload as exc:
        raise _bad(exc) from exc


@router.post("/lectures/{lecture_id}/map/generate")
def generate_map(course_id: str, lecture_id: str, ctx: AppContext = Depends(get_ctx)) -> JobInfo:
    lec = svc.get_lecture(ctx.storage, course_id, lecture_id)
    if lec.map_status in ("queued", "running") and lec.map_job_id:
        job = ctx.jobs.get(lec.map_job_id)
        if job and job.state in ("queued", "running"):
            return job
    log_usage(ctx, "map.generate")
    return start_map_job(ctx, course_id, lecture_id)


@router.get("/lectures/{lecture_id}/map")
def get_map(course_id: str, lecture_id: str, ctx: AppContext = Depends(get_ctx)) -> MapDoc:
    st = ctx.storage
    svc.get_lecture(st, course_id, lecture_id)
    path = st.paths.map(course_id, lecture_id)
    if not st.exists(path):
        raise HTTPException(404, "This lecture has no map yet.")
    return st.read_doc(path, MapDoc)


# --------------------------------------------------------------------------- sources shelf

@router.get("/sources")
def list_sources(course_id: str, ctx: AppContext = Depends(get_ctx)) -> list[SourceMeta]:
    return svc.list_sources(ctx.storage, course_id)


@router.post("/sources", status_code=201)
def upload_source(
    course_id: str,
    file: UploadFile = File(...),
    kind: SourceKind = Form("other"),
    ctx: AppContext = Depends(get_ctx),
) -> SourceMeta:
    try:
        meta = svc.add_source(ctx.storage, course_id, file.filename or "file.pdf", file.file, kind=kind)
    except svc.BadUpload as exc:
        raise _bad(exc) from exc
    log_usage(ctx, "source.upload")
    return meta


@router.patch("/sources/{source_id}")
def patch_source(course_id: str, source_id: str, body: SourcePatch, ctx: AppContext = Depends(get_ctx)) -> SourceMeta:
    svc.get_source(ctx.storage, course_id, source_id)
    return svc.update_source(ctx.storage, course_id, source_id, kind=body.kind)


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(course_id: str, source_id: str, ctx: AppContext = Depends(get_ctx)) -> None:
    meta = svc.get_source(ctx.storage, course_id, source_id)
    if meta.lecture_id:
        raise HTTPException(409, "This file belongs to a lecture. Delete the lecture first.")
    svc.delete_source(ctx.storage, course_id, source_id)


@router.get("/sources/{source_id}/slides")
def source_slides(course_id: str, source_id: str, ctx: AppContext = Depends(get_ctx)) -> SlidesDoc:
    meta = svc.get_source(ctx.storage, course_id, source_id)
    try:
        return extract_source(ctx.storage, course_id, meta)
    except ParseError as exc:
        raise _bad(exc) from exc


@router.get("/sources/{source_id}/slides/{slide}/thumb")
def slide_thumb(course_id: str, source_id: str, slide: int, ctx: AppContext = Depends(get_ctx)) -> Response:
    st = ctx.storage
    svc.get_source(st, course_id, source_id)
    path = st.paths.thumbnail(course_id, source_id, slide)
    if not st.exists(path):
        raise HTTPException(404, "No preview image for this slide.")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "max-age=3600"})


@router.get("/sources/{source_id}/file")
def source_file(course_id: str, source_id: str, ctx: AppContext = Depends(get_ctx)) -> Response:
    st = ctx.storage
    meta = svc.get_source(st, course_id, source_id)
    return FileResponse(st.paths.source_file(course_id, source_id, meta.ext), filename=meta.filename)
