"""用户—职位详情：职位实体 + 用户关系一并返回。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from entity.mongo.job import Job
from entity.mongo.user_job import UserJob


class UserJobView(BaseModel):
    """详情页用组合视图。"""

    model_config = ConfigDict(extra="ignore")

    job: Job = Field(description="职位主数据（jobs）")
    user_job: UserJob = Field(description="当前用户与该职位的关系（user_jobs）")
