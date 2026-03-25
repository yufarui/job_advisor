/** 用户事实列表（页面以表单行/字段展示） */

import type { FactView } from "../types";
import { httpJson } from "./http";

export function listFactsByUser(userId: string) {
  return httpJson<{ facts: FactView[] }>(
    `/api/facts/user/${encodeURIComponent(userId)}/list`,
  );
}
