from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from backend.api.deps import get_ctx
from backend.core import courses as svc
from backend.core.context import AppContext
from backend.core.schemas import Course, Lecture
from backend.core.usage import log_usage

router = APIRouter(prefix="/courses", tags=["courses"])


class CourseIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class CourseDetail(BaseModel):
    course: Course
    lectures: list[Lecture]


@router.get("")
def list_courses(ctx: AppContext = Depends(get_ctx)) -> list[Course]:
    return svc.list_courses(ctx.storage)


@router.post("", status_code=201)
def create_course(body: CourseIn, ctx: AppContext = Depends(get_ctx)) -> Course:
    log_usage(ctx, "course.create")
    return svc.create_course(ctx.storage, body.name)


@router.get("/{course_id}")
def get_course(course_id: str, ctx: AppContext = Depends(get_ctx)) -> CourseDetail:
    return CourseDetail(
        course=svc.get_course(ctx.storage, course_id),
        lectures=svc.list_lectures(ctx.storage, course_id),
    )


@router.patch("/{course_id}")
def rename_course(course_id: str, body: CourseIn, ctx: AppContext = Depends(get_ctx)) -> Course:
    return svc.rename_course(ctx.storage, course_id, body.name)


@router.delete("/{course_id}", status_code=204)
def delete_course(course_id: str, ctx: AppContext = Depends(get_ctx)) -> None:
    svc.delete_course(ctx.storage, course_id)
