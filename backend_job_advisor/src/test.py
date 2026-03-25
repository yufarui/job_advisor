from typing import Any, Optional
from entity.view.resume_update_request import ResumeUpdateToolInput
from entity.view.user_job_update_request import UserJobUpdateToolInput
from langchain_core.tools import BaseTool, tool

@tool(
    "updateJobs",
    args_schema=ResumeUpdateToolInput,
    infer_schema=False,
)
def updateJobs(**kwargs: Any) -> str:
    """测试工具"""
    return f"Hello!"

print(updateJobs.get_input_jsonschema())