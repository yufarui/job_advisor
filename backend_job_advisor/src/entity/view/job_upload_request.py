"""职位上传：单条与批量；图片字段由后端解析。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from constants.job_source_enum import JobSourceEnum


class JobUploadRequest(BaseModel):
    """单条职位录入（可与 multipart 图片配合）。"""

    model_config = ConfigDict(extra="ignore")

    title: str = Field(default="", description="职位名称")
    company: str = Field(default="", description="公司名")
    city: str = Field(default="", description="城市或地点")
    salary_range: str | None = Field(default=None, description="薪资展示文案")
    jd_text: str = Field(default="", description="职位描述正文")
    source: JobSourceEnum | None = Field(default=None, description="数据来源（枚举）")
    images: list[str] = Field(
        default_factory=list,
        description="图片：Base64 数据 URL 或对象存储 URL",
    )


class JobBulkUploadRequest(BaseModel):
    """批量上传职位。"""

    model_config = ConfigDict(extra="ignore")

    jobs: list[JobUploadRequest] = Field(
        default_factory=list,
        description="职位列表；无 biz_id 时由服务端生成",
    )


class JobBulkInsertResponse(BaseModel):
    """批量插入结果。"""

    model_config = ConfigDict(extra="ignore")

    inserted_ids: list[str] = Field(
        default_factory=list,
        description="Mongo 新建文档的 _id 列表",
    )
    count: int = Field(ge=0, description="成功插入条数")
