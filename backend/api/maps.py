from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from typing import Literal

from pydantic import BaseModel, Field

from backend.api.deps import get_ctx
from backend.core import maps as svc
from backend.core.context import AppContext
from backend.core.schemas import MapDoc, SlideRef, Status
from backend.core.usage import log_usage
from backend.pipeline.node_actions import Action, Proposal, suggest

router = APIRouter(prefix="/courses/{course_id}/lectures/{lecture_id}/map", tags=["map"])


class NodePatch(BaseModel):
    label: str | None = Field(default=None, max_length=200)
    status: Status | None = None
    status_mode: Literal["auto"] | None = None  # back to automatic (manual is set by choosing a status)
    studied: bool = False


class NewNode(BaseModel):
    parent_id: str
    label: str = Field(min_length=1, max_length=200)
    sources: list[SlideRef] = Field(default_factory=list)
    index: int | None = None


class AddedOut(BaseModel):
    map: MapDoc
    node_ids: list[str]


class SuggestIn(BaseModel):
    action: Action
    sibling_id: str | None = None


def _edit_error(exc: Exception) -> HTTPException:
    return HTTPException(400, str(exc))


@router.put("/structure")
def put_structure(course_id: str, lecture_id: str, tree: svc.TreeIn, ctx: AppContext = Depends(get_ctx)) -> MapDoc:
    try:
        return svc.apply_structure(ctx.storage, course_id, lecture_id, tree)
    except svc.MapEditError as exc:
        raise _edit_error(exc) from exc


@router.patch("/nodes/{node_id}")
def patch_node(course_id: str, lecture_id: str, node_id: str, body: NodePatch, ctx: AppContext = Depends(get_ctx)) -> MapDoc:
    if body.status is not None:
        log_usage(ctx, "node.status")
    try:
        doc = svc.patch_node(ctx.storage, course_id, lecture_id, node_id, label=body.label,
                             status=body.status, studied=body.studied, auto=body.status_mode == "auto")
    except svc.MapEditError as exc:
        raise _edit_error(exc) from exc
    if body.status_mode == "auto":
        from backend.core.status import recompute

        recompute(ctx.storage, course_id, lecture_id, [node_id])
        doc = svc.load_map(ctx.storage, course_id, lecture_id)
    return doc


@router.post("/nodes", status_code=201)
def add_node(course_id: str, lecture_id: str, body: NewNode, ctx: AppContext = Depends(get_ctx)) -> AddedOut:
    try:
        doc, ids = svc.add_nodes(ctx.storage, course_id, lecture_id, body.parent_id,
                                 [(body.label, body.sources)], index=body.index)
    except svc.MapEditError as exc:
        raise _edit_error(exc) from exc
    return AddedOut(map=doc, node_ids=ids)


@router.post("/nodes/{node_id}/suggest")
def suggest_action(course_id: str, lecture_id: str, node_id: str, body: SuggestIn,
                   ctx: AppContext = Depends(get_ctx)) -> Proposal:
    doc = svc.load_map(ctx.storage, course_id, lecture_id)
    log_usage(ctx, f"node.ai.{body.action}")
    try:
        return suggest(ctx.storage, ctx.provider, ctx.prompts, ctx.require_model("study"), course_id, doc,
                       node_id, body.action, body.sibling_id)
    except svc.MapEditError as exc:
        raise _edit_error(exc) from exc


@router.post("/apply")
def apply_proposal(course_id: str, lecture_id: str, p: Proposal, ctx: AppContext = Depends(get_ctx)) -> MapDoc:
    st = ctx.storage
    try:
        if p.action == "expand":
            doc, _ = svc.add_nodes(st, course_id, lecture_id, p.node_id,
                                   [(x.label, x.sources) for x in p.parts], origin="ai")
            return doc
        if p.action == "split":
            return svc.split_node(st, course_id, lecture_id, p.node_id, [(x.label, x.sources) for x in p.parts])
        if p.action == "merge":
            if not p.sibling_id or not p.label:
                raise svc.MapEditError("Merge needs a sibling and a label.")
            return svc.merge_nodes(st, course_id, lecture_id, p.node_id, p.sibling_id, p.label)
        if not p.label:
            raise svc.MapEditError("No label to apply.")
        return svc.patch_node(st, course_id, lecture_id, p.node_id, label=p.label)
    except svc.MapEditError as exc:
        raise _edit_error(exc) from exc


@router.post("/add-uncovered")
def add_uncovered(course_id: str, lecture_id: str, ctx: AppContext = Depends(get_ctx)) -> MapDoc:
    return svc.add_uncovered(ctx.storage, course_id, lecture_id)
