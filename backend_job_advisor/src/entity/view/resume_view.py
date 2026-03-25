"""简历详情 API 输出：与 Mongo user_resume 字段一致。"""

from __future__ import annotations

from entity.mongo.user_resume import UserResume


class ResumeView(UserResume):
    """供 GET 详情序列化；结构同 ``UserResume``。"""
