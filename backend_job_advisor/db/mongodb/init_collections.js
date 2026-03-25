/**
 * MongoDB：集合与索引初始化（无表/外键/枚举类型，仅用集合 + 索引）
 *
 * 使用（本地已启动 MongoDB）：
 *   mongosh "mongodb://localhost:27017/job_advisor" init_collections.js
 * 或在 mongosh 内：
 *   load("/path/to/init_collections.js")
 */

const dbName = "job_advisor";
const conn = db.getSiblingDB(dbName);

// ---------- tasks（主任务）----------
conn.createCollection("tasks");
conn.tasks.createIndex({ user_id: 1, created_at: -1 }, { name: "idx_tasks_user_created" });
conn.tasks.createIndex({ status: 1, created_at: -1 }, { name: "idx_tasks_status_created" });
conn.tasks.createIndex({ created_at: -1 }, { name: "idx_tasks_created" });

// ---------- sub_tasks（子任务）----------
conn.createCollection("sub_tasks");
conn.sub_tasks.createIndex({ task_id: 1, created_at: 1 }, { name: "idx_sub_tasks_task_created" });
conn.sub_tasks.createIndex({ task_id: 1, status: 1 }, { name: "idx_sub_tasks_task_status" });
conn.sub_tasks.createIndex({ tool_name: 1, created_at: -1 }, { name: "idx_sub_tasks_tool_created" });

// ---------- jobs（职位）----------
conn.createCollection("jobs");
conn.jobs.createIndex({ biz_id: 1 }, { name: "idx_jobs_biz_id", unique: true });
conn.jobs.createIndex({ title: "text", jd_text: "text" }, { name: "idx_jobs_text" });
conn.jobs.createIndex({ company: 1, city: 1 }, { name: "idx_jobs_company_city" });
conn.jobs.createIndex({ created_at: -1 }, { name: "idx_jobs_created" });

// ---------- user_jobs（用户—职位）----------
conn.createCollection("user_jobs");
conn.user_jobs.createIndex(
  { user_id: 1, job_id: 1 },
  { name: "idx_user_jobs_user_job", unique: true }
);
conn.user_jobs.createIndex(
  { user_id: 1, status: 1, updated_at: -1 },
  { name: "idx_user_jobs_user_status_updated" }
);

// ---------- user_resume（用户简历，一用户一份）----------
conn.createCollection("user_resume");
conn.user_resume.createIndex({ user_id: 1 }, { name: "idx_user_resume_user", unique: true });

print(`MongoDB [${dbName}] 集合与索引已创建或已存在（重复执行 createIndex 为幂等）。`);
