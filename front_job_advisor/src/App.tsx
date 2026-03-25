import { useEffect, useMemo, useState, type KeyboardEvent } from "react";
import { api, type NotifySsePayload } from "./api";
import type {
  Account,
  ChatHistoryItem,
  FactView,
  JobCard,
  JobDetail,
  MenuKey,
  ResumeView,
} from "./types";

type Msg = { role: "user" | "assistant"; content: string };
type JobStatusFilter =
  | "all"
  | "saved"
  | "viewed"
  | "applied"
  | "interviewing"
  | "offer"
  | "rejected"
  | "ignored"
  | "archived";
const JOB_STATUS_TABS: Array<{ value: JobStatusFilter; label: string }> = [
  { value: "all", label: "不限" },
  { value: "saved", label: "已保存" },
  { value: "viewed", label: "已查看" },
  { value: "applied", label: "已投递" },
  { value: "interviewing", label: "面试中" },
  { value: "offer", label: "Offer" },
  { value: "rejected", label: "已拒绝" },
  { value: "ignored", label: "已忽略" },
  { value: "archived", label: "已归档" },
];

const ACCOUNTS: Account[] = [
  { id: "dev", name: "开发" },
  { id: "test", name: "测试" },
];

function str(v: unknown): string {
  if (v === null || v === undefined) return "";
  return String(v);
}

function ReadOnlyRow({ label, value }: { label: string; value: string }) {
  return (
    <label className="form-row">
      <span className="form-label">{label}</span>
      <input className="form-input" readOnly value={value} />
    </label>
  );
}

function rowsToMsgs(rows: ChatHistoryItem[]): Msg[] {
  return rows
    .filter((x) => x.role === "user" || x.role === "assistant")
    .map((x) => ({ role: x.role as "user" | "assistant", content: x.content }));
}

function ResumeFormPanel({ data }: { data: ResumeView }) {
  const b = data.basic_info ?? {};
  const intent = data.job_intent ?? {};
  return (
    <div className="form-panel">
      <fieldset className="form-fieldset">
        <legend>基本信息</legend>
        <ReadOnlyRow label="用户 ID" value={data.user_id ?? ""} />
        <ReadOnlyRow label="邮箱" value={str(b.email)} />
        <ReadOnlyRow label="手机" value={str(b.phone)} />
        <ReadOnlyRow label="年龄" value={b.age != null ? String(b.age) : ""} />
        <ReadOnlyRow label="性别" value={str(b.gender)} />
      </fieldset>
      <fieldset className="form-fieldset">
        <legend>求职意向</legend>
        <ReadOnlyRow label="期望岗位" value={(intent.roles ?? []).join("、")} />
        <ReadOnlyRow label="期望城市" value={(intent.cities ?? []).join("、")} />
        <ReadOnlyRow label="期望薪资" value={str(intent.salary_expectation)} />
        <ReadOnlyRow label="工作方式" value={str(intent.work_mode)} />
      </fieldset>
      <fieldset className="form-fieldset">
        <legend>技能</legend>
        <ReadOnlyRow label="标签" value={(data.skills ?? []).join("、")} />
      </fieldset>
      <fieldset className="form-fieldset">
        <legend>工作经历</legend>
        {(data.work_experience ?? []).length === 0 ? (
          <p className="form-empty">暂无</p>
        ) : (
          (data.work_experience ?? []).map((w, i) => (
            <div key={i} className="form-repeat-block">
              <ReadOnlyRow label="公司" value={str(w.company)} />
              <ReadOnlyRow label="职位" value={str(w.title)} />
              <ReadOnlyRow label="起止" value={`${str(w.start_date)} — ${str(w.end_date)}`} />
              <label className="form-row form-row-stack">
                <span className="form-label">描述</span>
                <textarea className="form-textarea" readOnly value={str(w.description)} rows={3} />
              </label>
            </div>
          ))
        )}
      </fieldset>
      <fieldset className="form-fieldset">
        <legend>教育经历</legend>
        {(data.education ?? []).length === 0 ? (
          <p className="form-empty">暂无</p>
        ) : (
          (data.education ?? []).map((e, i) => (
            <div key={i} className="form-repeat-block">
              <ReadOnlyRow label="学校" value={str(e.school)} />
              <ReadOnlyRow label="学历" value={str(e.degree)} />
              <ReadOnlyRow label="专业" value={str(e.major)} />
              <ReadOnlyRow label="起止" value={`${str(e.start_date)} — ${str(e.end_date)}`} />
            </div>
          ))
        )}
      </fieldset>
    </div>
  );
}

function FactFormRow({ f }: { f: FactView }) {
  return (
    <fieldset className="fact-fieldset">
      <legend className="fact-legend">
        <span className="fact-no">{f.fact_no}</span>
        {f.confidence != null && (
          <span className="fact-confidence">置信度 {f.confidence.toFixed(2)}</span>
        )}
      </legend>
      <ReadOnlyRow label="谓词" value={f.predicate} />
      <ReadOnlyRow label="取值" value={f.value} />
      <label className="form-row form-row-stack">
        <span className="form-label">内容</span>
        <textarea className="form-textarea" readOnly value={f.content || ""} rows={3} />
      </label>
    </fieldset>
  );
}

export default function App() {
  const [menu, setMenu] = useState<MenuKey>("jobs");
  const [accountId, setAccountId] = useState(ACCOUNTS[0].id);
  const [jobStatus, setJobStatus] = useState<JobStatusFilter>("all");
  const [jobs, setJobs] = useState<JobCard[]>([]);
  const [resume, setResume] = useState<ResumeView | null>(null);
  const [facts, setFacts] = useState<FactView[]>([]);
  const [selectedFact, setSelectedFact] = useState<FactView | null>(null);
  const [selectedJob, setSelectedJob] = useState<JobDetail | null>(null);
  const [selectedJobBizId, setSelectedJobBizId] = useState("");
  const [jobDetailLoading, setJobDetailLoading] = useState(false);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [notify, setNotify] = useState<NotifySsePayload | null>(null);

  const accountName = useMemo(
    () => ACCOUNTS.find((a) => a.id === accountId)?.name ?? accountId,
    [accountId],
  );
  const accountAvatar = accountId === "test" ? "/avatar-bot-cartoon.svg" : "/avatar-user-cartoon.svg";

  const cycleAccount = () => {
    const idx = ACCOUNTS.findIndex((a) => a.id === accountId);
    const next = ACCOUNTS[(idx + 1) % ACCOUNTS.length];
    setAccountId(next.id);
  };

  useEffect(() => {
    const es = api.notify.openUserNotifyStream(accountId, (p) => setNotify(p));
    return () => es.close();
  }, [accountId]);

  useEffect(() => {
    let mounted = true;
    api.chat
      .getHistory(accountId)
      .then((rows) => {
        if (!mounted) return;
        setMessages(rowsToMsgs(rows));
      })
      .catch(() => {
        if (!mounted) return;
        setMessages([]);
      });
    return () => {
      mounted = false;
    };
  }, [accountId]);

  useEffect(() => {
    let mounted = true;
    setError("");
    const run = async () => {
      try {
        if (menu === "jobs") {
          const r = await api.jobs.listCards(
            accountId,
            jobStatus === "all" ? undefined : jobStatus,
          );
          if (!mounted) return;
          setJobs(r.cards);
          return;
        }
        if (menu === "resume") {
          const r = await api.resumes.getDetail(accountId).catch(() => null);
          if (!mounted) return;
          setResume(r);
          return;
        }
        if (menu === "facts") {
          const r = await api.facts.listByUser(accountId).catch(() => ({ facts: [] as FactView[] }));
          if (!mounted) return;
          setFacts(r.facts);
          return;
        }
      } catch (e) {
        if (mounted) setError(String(e));
      }
    };
    void run();
    return () => {
      mounted = false;
    };
  }, [accountId, jobStatus, menu]);

  const send = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setLoading(true);
    setError("");
    setMessages((m) => [...m, { role: "user", content: text }]);
    setInput("");
    try {
      const r = await api.chat.turn(accountId, text);
      setMessages((m) => [
        ...m,
        { role: "assistant", content: r.reply || "（无回复）" },
      ]);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  const onInputKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void send();
    }
  };
  const openJobDetail = async (bizId: string) => {
    setSelectedJobBizId(bizId);
    setJobDetailLoading(true);
    setSelectedJob(null);
    setError("");
    try {
      const detail = await api.jobs.getDetail(accountId, bizId);
      setSelectedJob(detail);
    } catch (e) {
      setError(String(e));
    } finally {
      setJobDetailLoading(false);
    }
  };

  return (
    <div className="app">
      <header className="top-banner">
        <div className="brand">
          <img src="/career-logo.svg" alt="求职顾问 Logo" className="brand-logo" />
          <h1>求职顾问</h1>
        </div>
        <div className="banner-right">
          <button className="account-avatar-btn" onClick={cycleAccount} title="点击切换账号">
            <img src={accountAvatar} className="account-avatar" alt="账号头像" />
            <span>{accountName}</span>
          </button>
        </div>
      </header>

      <div className="page">
        <aside className="menu">
        {([
          ["jobs", "职位信息", "💼"],
          ["resume", "简历信息", "📄"],
          ["facts", "事实", "🧠"],
        ] as const).map(([k, label, icon]) => (
          <button
            key={k}
            className={menu === k ? "active" : ""}
            onClick={() => setMenu(k)}
            title={label}
          >
            <span className="menu-icon">{icon}</span>
            <span>{label}</span>
          </button>
        ))}
        </aside>

        <main className="main">
          {notify && (
            <div className={`notify-strip sev-${notify.severity ?? "info"}`} role="status">
              <span className="notify-msg">{notify.message}</span>
              <button type="button" className="notify-dismiss" onClick={() => setNotify(null)} aria-label="关闭">
                ×
              </button>
            </div>
          )}
          {error && <div className="error">{error}</div>}
          {menu === "jobs" && (
            <section className="job-board">
              <div className="job-status-nav">
                {JOB_STATUS_TABS.map((tab) => (
                  <button
                    key={tab.value}
                    className={jobStatus === tab.value ? "active" : ""}
                    onClick={() => setJobStatus(tab.value)}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
              <div className="job-cards">
                {jobs.map((j) => (
                  <article
                    key={j.biz_id}
                    className="job-card job-card-clickable"
                    onClick={() => void openJobDetail(j.biz_id)}
                    role="button"
                    tabIndex={0}
                  >
                    <header className="job-card-head">
                      <h2 className="job-card-title">{j.title}</h2>
                      {j.status && <span className="job-card-badge">{j.status}</span>}
                    </header>
                    <div className="job-card-company">{j.company}</div>
                    <div className="job-card-bizid">biz_id: {j.biz_id}</div>
                    <dl className="job-card-meta">
                      {j.city && (
                        <>
                          <dt>城市</dt>
                          <dd>{j.city}</dd>
                        </>
                      )}
                      {j.salary_range && (
                        <>
                          <dt>薪资</dt>
                          <dd>{j.salary_range}</dd>
                        </>
                      )}
                      {j.attention_level != null && (
                        <>
                          <dt>关注度</dt>
                          <dd>{j.attention_level}</dd>
                        </>
                      )}
                    </dl>
                    {j.note && <p className="job-card-note">{j.note}</p>}
                  </article>
                ))}
              </div>
            </section>
          )}
          {menu === "resume" && (
            <section className="resume-section">
              {resume ? (
                <ResumeFormPanel data={resume} />
              ) : (
                <p className="form-empty">暂无简历数据（后端无记录或加载失败）。</p>
              )}
            </section>
          )}
          {menu === "facts" && (
            <section className="facts-card-list">
              {facts.length === 0 ? (
                <p className="form-empty">暂无事实。</p>
              ) : (
                facts.map((f) => (
                  <article
                    key={f.fact_no}
                    className="fact-card"
                    onClick={() => setSelectedFact(f)}
                    role="button"
                    tabIndex={0}
                  >
                    <div className="fact-card-predicate">{f.predicate}</div>
                    <div className="fact-card-value">{f.value || "（空）"}</div>
                  </article>
                ))
              )}
            </section>
          )}
        </main>

        <section className="chat">
          <h2>对话智能体</h2>
          <div className="msgs">
            {messages.map((m, i) => (
              <div key={i} className={`msg-row ${m.role}`}>
                <img
                  className="msg-avatar"
                  src={m.role === "user" ? "/avatar-user-cartoon.svg" : "/avatar-bot-cartoon.svg"}
                  alt={m.role === "user" ? "用户头像" : "系统头像"}
                />
                <div className={`msg ${m.role}`}>
                  <div>{m.content}</div>
                </div>
              </div>
            ))}
          </div>
          <div className="input">
            <textarea
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={onInputKeyDown}
              placeholder="输入对话内容..."
            />
            <button disabled={loading} onClick={send}>
              {loading ? "发送中..." : "发送"}
            </button>
          </div>
        </section>
      </div>
      {selectedFact && (
        <div className="modal-mask" onClick={() => setSelectedFact(null)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <h3>事实详情</h3>
              <button onClick={() => setSelectedFact(null)}>关闭</button>
            </div>
            <FactFormRow f={selectedFact} />
          </div>
        </div>
      )}
      {(jobDetailLoading || selectedJob) && (
        <div className="modal-mask" onClick={() => (!jobDetailLoading ? setSelectedJob(null) : undefined)}>
          <div className="modal-panel" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <h3>职位详情 {selectedJobBizId ? `(${selectedJobBizId})` : ""}</h3>
              {!jobDetailLoading && <button onClick={() => setSelectedJob(null)}>关闭</button>}
            </div>
            {jobDetailLoading ? (
              <p className="form-empty">加载中...</p>
            ) : (
              <pre className="detail-json">
                {JSON.stringify(selectedJob, null, 2)}
              </pre>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
