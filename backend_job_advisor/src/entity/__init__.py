"""实体包：Mongo 文档、API 视图、领域模型与 Redis 消息结构。

供后端序列化与（通过 JSON Schema）供大模型理解接口契约时使用。"""

from entity.document.fact_document import FactDocument
from entity.domain.fact_domain import Fact
from entity.mongo.job import Job
from entity.mongo.resume_basic_info import ResumeBasicInfo
from entity.mongo.resume_education import ResumeEducation
from entity.mongo.resume_job_intent import ResumeJobIntent
from entity.mongo.resume_work_experience import ResumeWorkExperience
from entity.mongo.sub_task import SubTask
from entity.mongo.task import Task
from entity.mongo.user_job import UserJob
from entity.mongo.user_job_query_filter import UserJobQueryFilter
from entity.mongo.user_resume import UserResume
from entity.redis.dialogue_message import DialogueMessage
from entity.redis.redis_dialogue_key import RedisDialogueKey

__all__ = [
    "DialogueMessage",
    "Fact",
    "FactDocument",
    "Job",
    "RedisDialogueKey",
    "ResumeBasicInfo",
    "ResumeEducation",
    "ResumeJobIntent",
    "ResumeWorkExperience",
    "SubTask",
    "Task",
    "UserJob",
    "UserJobQueryFilter",
    "UserResume",
]
