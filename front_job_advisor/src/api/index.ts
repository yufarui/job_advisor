/**
 * API 客户端入口：按领域拆分为 job / resume / fact / chat / notify。
 * 兼容原有 `import { api } from "./api"`。
 */
import { fetchChatGraph, fetchChatHistory, postChatTurn } from "./chat";
import { listFactsByUser } from "./fact";
import { getJobDetail, listJobCards } from "./job";
import { openUserNotifyStream, pushNotify } from "./notify";
import { getResumeDetail } from "./resume";

export { fetchChatGraph, fetchChatHistory, postChatTurn } from "./chat";
export { listFactsByUser } from "./fact";
export { httpJson } from "./http";
export { getJobDetail, listJobCards } from "./job";
export { openUserNotifyStream, pushNotify } from "./notify";
export type { NotifyPushBody, NotifySsePayload } from "./notify";
export { getResumeDetail } from "./resume";

export const api = {
  jobs: { listCards: listJobCards, getDetail: getJobDetail },
  resumes: { getDetail: getResumeDetail },
  facts: { listByUser: listFactsByUser },
  chat: { turn: postChatTurn, getGraph: fetchChatGraph, getHistory: fetchChatHistory },
  notify: { openUserNotifyStream, pushNotify },
};
