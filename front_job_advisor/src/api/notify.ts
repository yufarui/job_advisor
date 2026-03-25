/** SSE 通知 + 测试推送（与 notify_api 对齐） */

import { httpJson } from "./http";

export type NotifySsePayload = {
  message: string;
  severity?: string;
  event_type?: string;
  ts?: string;
};

/** 建立用户维度的 SSE；回调收到服务端 JSON 负载 */
export function openUserNotifyStream(
  userId: string,
  onEvent: (payload: NotifySsePayload) => void,
): EventSource {
  const url = `/api/notify/user/${encodeURIComponent(userId)}/stream`;
  const es = new EventSource(url);
  es.onmessage = (ev) => {
    try {
      const payload = JSON.parse(ev.data) as NotifySsePayload;
      onEvent(payload);
    } catch {
      /* 忽略非 JSON ping 等 */
    }
  };
  return es;
}

export type NotifyPushBody = {
  message: string;
  severity?: string;
  event_type?: string;
};

/** 开发/联调用：向指定用户推送一条通知 */
export function pushNotify(userId: string, body: NotifyPushBody) {
  return httpJson<{ delivered: number }>(
    `/api/notify/user/${encodeURIComponent(userId)}/push`,
    {
      method: "POST",
      body: JSON.stringify(body),
    },
  );
}
