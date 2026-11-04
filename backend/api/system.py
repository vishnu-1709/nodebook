from __future__ import annotations

import json
import platform
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

import psutil
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel

from backend.api.deps import get_ctx
from backend.core.context import AppContext
from backend.core.courses import get_course
from backend.core.jobs import JobContext, JobInfo
from backend.core.resources import config_dir
from backend.core.schemas import SlideRef
from backend.core.transfer import ImportError_, export_course, import_course
from backend.core.usage import log_usage
from backend.llm.base import LLMError, PullProgress
from backend.pipeline.map_builder import BuildInput, DeckSlide, MapBuilder
from backend.pipeline.parse_pdf import ParseError, parse_pdf
from backend.pipeline.parse_pptx import parse_pptx

router = APIRouter(tags=["system"])
VERSION = "0.2.0"


class SystemOut(BaseModel):
    version: str
    ram_gb: float
    platform: str
    data_dir: str
    onboarded: bool


class RecModel(BaseModel):
    name: str
    size_gb: float = 0
    why: str = ""
    vision: bool = False
    installed: bool = False


class RecOut(BaseModel):
    ram_gb: float
    tier_label: str
    map: list[RecModel]
    study: list[RecModel]


class PullIn(BaseModel):
    name: str


def ram_gb() -> float:
    return round(psutil.virtual_memory().total / 1024**3, 1)


def load_recommendations() -> dict[str, Any]:
    return json.loads((config_dir() / "recommended_models.json").read_text("utf-8"))


@router.get("/system")
def system(ctx: AppContext = Depends(get_ctx)) -> SystemOut:
    return SystemOut(version=VERSION, ram_gb=ram_gb(), platform=platform.system(),
                     data_dir=str(ctx.data_dir), onboarded=ctx.settings.onboarded)


@router.get("/models/recommended")
def recommended(ctx: AppContext = Depends(get_ctx)) -> RecOut:
    ram = ram_gb()
    tiers = sorted(load_recommendations()["tiers"], key=lambda t: t["min_ram_gb"])
    tier = tiers[0]
    for t in tiers:
        if ram >= t["min_ram_gb"]:
            tier = t
    try:
        installed = {m.name for m in ctx.provider.list_models()}
    except LLMError:
        installed = set()

    def mark(items: list[dict[str, Any]]) -> list[RecModel]:
        out = []
        for it in items:
            m = RecModel(**it)
            m.installed = m.name in installed or f"{m.name}:latest" in installed
            out.append(m)
        return out

    return RecOut(ram_gb=ram, tier_label=tier["label"], map=mark(tier["map"]), study=mark(tier["study"]))


@router.post("/ollama/pull")
def pull(body: PullIn, ctx: AppContext = Depends(get_ctx)) -> JobInfo:
    provider = ctx.provider
    name = body.name.strip()
    if not name:
        raise HTTPException(400, "Model name is empty.")
    log_usage(ctx, "ollama.pull")

    def run(job: JobContext) -> dict[str, Any]:
        def on(p: PullProgress) -> None:
            frac = p.completed / p.total if p.total else 0.0
            msg = p.status
            if p.total:
                msg = f"{p.status} · {p.completed / 1024**3:.1f} / {p.total / 1024**3:.1f} GB"
            job.report("pull", frac, msg)

        provider.pull(name, on)
        return {"model": name}

    return ctx.jobs.submit("pull", run)


@router.post("/ollama/test-map")
def test_map(file: UploadFile = File(...), ctx: AppContext = Depends(get_ctx)) -> JobInfo:
    """"Test on my slides": build a map from a deck without saving anything."""
    name = file.filename or "deck.pdf"
    ext = name.rsplit(".", 1)[-1].lower()
    if ext not in ("pdf", "pptx"):
        raise HTTPException(400, "Use a PDF or PPTX deck.")
    tmp = Path(tempfile.mkdtemp(prefix="nodebook-test-")) / f"deck.{ext}"
    with open(tmp, "wb") as fh:
        while chunk := file.file.read(1024 * 1024):
            fh.write(chunk)
    model = ctx.require_model("map")
    provider, prompts = ctx.provider, ctx.prompts
    log_usage(ctx, "ollama.test_map")

    def run(job: JobContext) -> dict[str, Any]:
        t0 = time.monotonic()
        try:
            slides = parse_pdf(tmp) if ext == "pdf" else parse_pptx(tmp)
        except ParseError as exc:
            tmp.unlink(missing_ok=True)
            raise LLMError(str(exc)) from exc
        deck = [DeckSlide(SlideRef(source_id="TEST", slide=s.number), s) for s in slides]
        res = MapBuilder(provider, prompts).build(
            BuildInput(lecture_id="TEST", lecture_title=name.rsplit(".", 1)[0], slides=deck, model=model),
            progress=lambda step, prog, msg: job.report(step, prog, msg),
        )
        doc = res.map
        lines: list[str] = []

        def walk(nid: str, depth: int) -> None:
            n = doc.nodes[nid]
            lines.append(("  " * depth) + n.label)
            for c in n.children:
                walk(c, depth + 1)

        walk(doc.root_id, 0)
        tmp.unlink(missing_ok=True)
        return {"outline": lines, "nodes": len(doc.nodes), "uncovered": [u.slide for u in res.uncovered],
                "fallback": res.fallback, "seconds": round(time.monotonic() - t0, 1), "model": model}

    return ctx.jobs.submit("test_map", run)


@router.post("/system/open-data-folder", status_code=204)
def open_data_folder(ctx: AppContext = Depends(get_ctx)) -> None:
    path = str(ctx.data_dir)
    try:
        if sys.platform.startswith("win"):
            subprocess.Popen(["explorer", path])  # noqa: S603, S607
        elif sys.platform == "darwin":
            subprocess.Popen(["open", path])  # noqa: S603, S607
        else:
            subprocess.Popen(["xdg-open", path])  # noqa: S603, S607
    except OSError as exc:
        raise HTTPException(500, f"Couldn't open the folder: {exc}. It is at {path}") from exc


@router.get("/courses/{course_id}/export")
def export(course_id: str, ctx: AppContext = Depends(get_ctx)) -> Response:
    course = get_course(ctx.storage, course_id)
    data = export_course(ctx.storage, course_id)
    safe = "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in course.name).strip() or "course"
    return Response(data, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{safe}.nodebook.zip"'})


@router.post("/courses/import", status_code=201)
async def import_(file: UploadFile = File(...), ctx: AppContext = Depends(get_ctx)) -> dict[str, str]:
    data = await file.read()
    try:
        cid = import_course(ctx.storage, data)
    except ImportError_ as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"course_id": cid}


