/** 职位卡片列表（主区域以卡片形态展示） */

import type { JobCard } from "../types";
import { httpJson } from "./http";

export function listJobCards(userId: string, status?: string) {
  const q = new URLSearchParams({ user_id: userId });
  if (status) q.set("status", status);
  return httpJson<{ cards: JobCard[] }>(`/api/jobs/cards?${q.toString()}`);
}

export function getJobDetail(userId: string, bizId: string) {
  return httpJson<{ job: Record<string, unknown>; user_job: Record<string, unknown> }>(
    `/api/jobs/user/${encodeURIComponent(userId)}/biz/${encodeURIComponent(bizId)}/detail`,
  );
}
