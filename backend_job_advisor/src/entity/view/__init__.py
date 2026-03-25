"""视图模型：与 HTTP 接口、前端页面字段一一对应。"""

from entity.view.job_cards_query import JobCardsQuery
from entity.view.job_update_request import JobUpdateRequest, JobUpdateResponse
from entity.view.job_upload_request import (
    JobBulkInsertResponse,
    JobBulkUploadRequest,
    JobUploadRequest,
)
from entity.view.fact_api_models import (
    BackendFactUpsertRequest,
    BackendFactUpsertResponse,
    FactBulkInsertRequest,
    FactBulkInsertResponse,
    FactDialogueSearchRequest,
    FactPageBulkAddResult,
    UserFactListResponse,
)
from entity.view.resume_update_request import ResumeUpdateRequest, ResumeUpdateResponse
from entity.view.resume_upload_request import ResumeUploadRequest
from entity.view.resume_view import ResumeView
from entity.view.user_fact_update_request import FactUpdateResponse, UserFactUpdateRequest
from entity.view.user_fact_view import UserFactView
from entity.view.user_job_card import UserJobCard, UserJobCardListResponse
from entity.view.user_job_update_request import UserJobUpdateRequest, UserJobUpdateResponse
from entity.view.user_job_view import UserJobView

__all__ = [
    "BackendFactUpsertRequest",
    "BackendFactUpsertResponse",
    "FactBulkInsertRequest",
    "FactBulkInsertResponse",
    "FactDialogueSearchRequest",
    "FactPageBulkAddResult",
    "FactUpdateResponse",
    "JobBulkInsertResponse",
    "JobBulkUploadRequest",
    "JobCardsQuery",
    "JobUpdateRequest",
    "JobUpdateResponse",
    "JobUploadRequest",
    "ResumeUpdateRequest",
    "ResumeUpdateResponse",
    "ResumeUploadRequest",
    "ResumeView",
    "UserFactListResponse",
    "UserFactUpdateRequest",
    "UserFactView",
    "UserJobCard",
    "UserJobCardListResponse",
    "UserJobUpdateRequest",
    "UserJobUpdateResponse",
    "UserJobView",
]
