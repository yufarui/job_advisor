"""职位 / 用户职位：仅保留约定接口，入参出参与 ``entity.view`` 对齐。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from constants.job_source_enum import JobSourceEnum
from entity.mongo.job import Job
from entity.view.job_cards_query import JobCardsQuery
from entity.view.job_update_request import JobUpdateRequest, JobUpdateResponse
from entity.view.job_upload_request import (
    JobBulkInsertResponse,
    JobBulkUploadRequest,
    JobUploadRequest,
)
from entity.view.user_job_card import UserJobCardListResponse
from entity.view.user_job_update_request import UserJobUpdateRequest, UserJobUpdateResponse
from entity.view.user_job_view import UserJobView
from service.job_service import JobService, get_job_service

JobServiceDep = Annotated[JobService, Depends(get_job_service)]

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _job_from_upload(req: JobUploadRequest) -> Job:
    return Job(
        biz_id="",
        source=req.source or JobSourceEnum.user_import,
        title=req.title,
        company=req.company,
        city=req.city,
        salary_range=req.salary_range,
        jd_text=req.jd_text,
    )


@router.get("/cards", response_model=UserJobCardListResponse)
async def get_user_job_cards(
    q: Annotated[JobCardsQuery, Query()],
    svc: JobServiceDep,
) -> UserJobCardListResponse:
    cards = await svc.list_user_job_cards(
        user_id=q.user_id,
        status=q.status,
        created_from=q.created_from,
        created_to=q.created_to,
    )
    return UserJobCardListResponse(cards=cards)


@router.get(
    "/user/{user_id}/biz/{biz_id}/detail",
    response_model=UserJobView,
)
async def get_user_job_detail(
    user_id: str,
    biz_id: str,
    svc: JobServiceDep,
) -> UserJobView:
    view = await svc.get_user_job_view(user_id, biz_id)
    if view is None:
        raise HTTPException(status_code=404, detail="user_job or job not found")
    return view


@router.post("/bulk", response_model=JobBulkInsertResponse)
async def post_insert_jobs(
    body: JobBulkUploadRequest,
    svc: JobServiceDep,
) -> JobBulkInsertResponse:
    if not body.jobs:
        raise HTTPException(status_code=400, detail="jobs must not be empty")
    jobs = [_job_from_upload(j) for j in body.jobs]
    ids = await svc.insert_jobs(jobs)
    return JobBulkInsertResponse(inserted_ids=ids, count=len(ids))


@router.patch("/update", response_model=JobUpdateResponse)
async def patch_update_job(
    body: JobUpdateRequest,
    svc: JobServiceDep,
) -> JobUpdateResponse:
    ok = await svc.update_jobs_with_biz_id(body)
    if not ok:
        raise HTTPException(status_code=404, detail="job not found or no change")
    return JobUpdateResponse()


router_user_jobs = APIRouter(prefix="/user-jobs", tags=["user-jobs"])


@router_user_jobs.patch("/update", response_model=UserJobUpdateResponse)
async def patch_update_user_job(
    body: UserJobUpdateRequest,
    svc: JobServiceDep,
) -> UserJobUpdateResponse:
    ok = await svc.update_user_jobs_with_biz_id(body)
    if not ok:
        raise HTTPException(status_code=404, detail="user_job not found or no change")
    return UserJobUpdateResponse()
