/** 简历详情（页面以只读表单/字段组展示） */

import type { ResumeView } from "../types";
import { httpJson } from "./http";

export function getResumeDetail(userId: string) {
  return httpJson<ResumeView>(`/api/resumes/user/${encodeURIComponent(userId)}/detail`);
}
