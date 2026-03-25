"""tool_slot_clarify：追问文案由硬规则生成（设计文档 §6.2 / Plan 细则）。"""

from __future__ import annotations

_TOOL_NAME_CN: dict[str, str] = {
    "searchJobs": "职位搜索",
    "searchResume": "简历查询",
    "searchCompany": "公司查询",
    "updateJobs": "求职记录更新",
    "updateResume": "简历更新",
    "notifyUser": "用户通知",
}


def _tool_display_name(tool_name: str | None, fallback: str | None) -> str:
    raw = (tool_name or fallback or "当前操作").strip()
    if not raw:
        return "当前操作"
    zh = _TOOL_NAME_CN.get(raw)
    return f"{zh}（{raw}）" if zh else raw


def build_slot_clarify_message(
    *,
    slot_key: str | None,
    missing_for_tool: str | None,
    tool_name: str | None,
) -> str:
    """根据槽位键生成固定模板话术，避免模型自由发挥。"""
    sk = (slot_key or "").strip()
    tool = _tool_display_name(tool_name, missing_for_tool)

    templates: dict[str, str] = {
        "biz_ids": f"为完成「{tool}」，请提供职位业务编号或标题。",
        "title": f"为完成「{tool}」，请说明要搜索的职位名称或关键词。",
        "company_name": f"为完成「{tool}」，请提供要查询的公司全称或常用简称。",
        "message": f"为完成「{tool}」，请补充需要通知用户的具体文案要点。",
        "patch_json": f"为完成「{tool}」，请按工具参数结构补充简历片段（如 basic_info、job_intent、skills 等），或稍后按页面表单修改。",
        "basic_info": f"为完成「{tool}」，请补充或确认基本信息（邮箱、手机、年龄、性别等）。",
        "work_experience": f"为完成「{tool}」，请补充工作经历（公司、职位、时间范围、描述等）。",
        "education": f"为完成「{tool}」，请补充教育经历（学校、学历、专业、时间等）。",
        "skills": f"为完成「{tool}」，请列出要写入或调整的技能标签。",
        "job_intent": f"为完成「{tool}」，请补充求职意向（期望岗位、城市、薪资、工作方式等）。",
        "user_id": "会话已绑定用户；若需代其他用户操作，请说明场景以便人工处理。",
    }

    if sk in templates:
        return templates[sk]
    if sk:
        return f"为完成「{tool}」，请补充以下信息：{sk}。"
    return f"为完成「{tool}」，还需要您补充一项关键信息后才能继续。"
