from constants.job_source_enum import JobSourceEnum


class BizConstant:
    TASKS_COLLECTION = "tasks"
    JOBS_COLLECTION = "jobs"
    USER_JOBS_COLLECTION = "user_jobs"
    USER_RESUME_COLLECTION = "user_resume"
    SUB_TASKS_COLLECTION = "sub_tasks"
    DIALOGUE_HISTORY_COLLECTION = "dialogue_history"

    _BIZ_LETTER: dict[JobSourceEnum, str] = {
        JobSourceEnum.internal: "I",
        JobSourceEnum.crawler: "C",
        JobSourceEnum.partner_api: "P",
        JobSourceEnum.user_import: "U",
        JobSourceEnum.unknown: "X",
    }
