export type MenuKey = "jobs" | "resume" | "facts";

export type Account = {
  id: string;
  name: string;
};

export type JobCard = {
  biz_id: string;
  title: string;
  company: string;
  city?: string;
  salary_range?: string;
  status?: string;
  attention_level?: number;
  note?: string;
};

export type JobDetail = {
  job: Record<string, unknown>;
  user_job: Record<string, unknown>;
};

export type ResumeBasicInfo = {
  age?: number | null;
  email?: string | null;
  phone?: string | null;
  gender?: string | null;
};

export type ResumeWorkExperience = {
  company?: string | null;
  title?: string | null;
  start_date?: string | null;
  end_date?: string | null;
  description?: string | null;
};

export type ResumeEducation = {
  school?: string | null;
  degree?: string | null;
  major?: string | null;
  start_date?: string | null;
  end_date?: string | null;
};

export type ResumeJobIntent = {
  roles?: string[];
  cities?: string[];
  salary_expectation?: string | null;
  work_mode?: string | null;
};

/** 与后端 ``ResumeView`` / ``user_resume`` 对齐，供表单只读展示 */
export type ResumeView = {
  id?: string | null;
  user_id?: string;
  basic_info?: ResumeBasicInfo;
  work_experience?: ResumeWorkExperience[];
  education?: ResumeEducation[];
  skills?: string[];
  job_intent?: ResumeJobIntent;
  created_at?: string | null;
  updated_at?: string | null;
};

export type FactView = {
  fact_no: string;
  predicate: string;
  value: string;
  content: string;
  confidence?: number;
};

export type ChatTurnResponse = {
  task_id?: string;
  task_is_new?: boolean;
  reply?: string;
  warnings?: string[];
  errors?: string[];
};

export type ChatHistoryItem = {
  user_id: string;
  task_id: string;
  role: "user" | "assistant" | "system" | string;
  content: string;
  ts?: string | null;
};
