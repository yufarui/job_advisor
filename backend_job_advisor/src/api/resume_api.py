"""简历：入参出参与 ``entity.view`` 对齐。"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from entity.view.resume_update_request import ResumeUpdateRequest, ResumeUpdateResponse
from entity.view.resume_upload_request import ResumeUploadRequest
from entity.view.resume_view import ResumeView
from service.resume_service import ResumeService, get_resume_service

ResumeServiceDep = Annotated[ResumeService, Depends(get_resume_service)]

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.get("/user/{user_id}/detail", response_model=ResumeView)
async def get_resume_detail(
    user_id: str,
    svc: ResumeServiceDep,
) -> ResumeView:
    view = await svc.get_resume_view(user_id)
    if view is None:
        raise HTTPException(status_code=404, detail="resume not found")
    return view


@router.post("/upload", response_model=ResumeView)
async def post_resume_upload(
    body: ResumeUploadRequest,
    svc: ResumeServiceDep,
) -> ResumeView:
    return await svc.upsert_resume_from_upload(body)


@router.patch("/update", response_model=ResumeUpdateResponse)
async def patch_resume_update(
    body: ResumeUpdateRequest,
    svc: ResumeServiceDep,
) -> ResumeUpdateResponse:
    ok = await svc.update_resume(body)
    if not ok:
        raise HTTPException(status_code=404, detail="resume not found or no change")
    return ResumeUpdateResponse()
