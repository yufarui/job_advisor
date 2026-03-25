/** 对话轮次与 Agent 图（侧栏对话区） */

import type { ChatHistoryItem, ChatTurnResponse } from "../types";
import { httpJson } from "./http";

export function postChatTurn(userId: string, message: string) {
  return httpJson<ChatTurnResponse>("/api/chat/turn", {
    method: "POST",
    body: JSON.stringify({ user_id: userId, message }),
  });
}

export function fetchChatGraph() {
  return httpJson<{ graph: string }>("/api/chat/graph");
}

export function fetchChatHistory(userId: string) {
  const q = new URLSearchParams({ user_id: userId });
  return httpJson<ChatHistoryItem[]>(`/api/chat/history?${q.toString()}`);
}
