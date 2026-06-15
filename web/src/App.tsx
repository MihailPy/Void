import { useEffect, useState } from "react";
import {
  Approval,
  Capability,
  HealthResponse,
  MemoryResponse,
  SchedulerStatusResponse,
  ScheduledTask,
  Skill,
  approve,
  clearStoredToken,
  createTask,
  deleteTask,
  disableTask,
  enableTask,
  getApprovals,
  getCapabilities,
  getFactsMemory,
  getProjectMemory,
  getSchedulerStatus,
  getSessionMemory,
  getSkills,
  getTasks,
  getStoredToken,
  health,
  reject,
  runDueTasksNow,
  runTask,
  sendChatMessage,
  setStoredToken,
} from "./api";

type Tab = "chat" | "approvals" | "tasks" | "capabilities" | "skills" | "memory";

type Message = {
  role: "user" | "void";
  content: string;
};

const tabs: { id: Tab; label: string }[] = [
  { id: "chat", label: "Chat" },
  { id: "approvals", label: "Approvals" },
  { id: "tasks", label: "Tasks" },
  { id: "capabilities", label: "Capabilities" },
  { id: "skills", label: "Skills" },
  { id: "memory", label: "Memory" },
];

function getErrorMessage(error: unknown) {
  return error instanceof Error ? error.message : "Unknown error";
}

function JsonBlock({ value }: { value: unknown }) {
  return <pre className="jsonBlock">{JSON.stringify(value, null, 2)}</pre>;
}

function EmptyState({ children }: { children: string }) {
  return <div className="empty">{children}</div>;
}

function StatusPanel() {
  const [status, setStatus] = useState<HealthResponse | null>(null);
  const [error, setError] = useState("");

  async function loadStatus() {
    try {
      setError("");
      setStatus(await health());
    } catch (currentError) {
      setStatus(null);
      setError(getErrorMessage(currentError));
    }
  }

  useEffect(() => {
    void loadStatus();
  }, []);

  return (
    <section className="statusPanel">
      <div className="sectionLabel">API status</div>
      <div className={status?.ok ? "status ok" : "status bad"}>
        <span className="statusDot" />
        {status?.ok ? "ok" : "offline"}
      </div>
      {status ? (
        <div className="muted">
          {status.service} · {status.version}
        </div>
      ) : null}
      {error ? <div className="sidebarError">{error}</div> : null}
      <button className="secondaryButton" type="button" onClick={loadStatus}>
        Refresh
      </button>
    </section>
  );
}

function AuthPanel() {
  const [token, setToken] = useState(() => getStoredToken());
  const [savedToken, setSavedToken] = useState(() => getStoredToken());

  function handleSave() {
    const nextToken = token.trim();
    if (nextToken) {
      setStoredToken(nextToken);
      setToken(nextToken);
      setSavedToken(nextToken);
    } else {
      clearStoredToken();
      setSavedToken("");
    }
  }

  function handleClear() {
    clearStoredToken();
    setToken("");
    setSavedToken("");
  }

  return (
    <section className="authPanel">
      <div className="sectionLabel">Auth</div>
      <div className={savedToken ? "authStatus saved" : "authStatus"}>
        {savedToken ? "Token saved" : "No token configured"}
      </div>
      <input
        aria-label="API token"
        autoComplete="off"
        type="password"
        value={token}
        onChange={(event) => setToken(event.target.value)}
        placeholder="API token"
      />
      <div className="authActions">
        <button type="button" onClick={handleSave}>
          Save
        </button>
        <button className="secondaryButton" type="button" onClick={handleClear}>
          Clear
        </button>
      </div>
    </section>
  );
}

function ChatTab() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function handleSend() {
    const message = input.trim();
    if (!message || loading) {
      return;
    }

    setInput("");
    setError("");
    setLoading(true);
    setMessages((current) => [...current, { role: "user", content: message }]);

    try {
      const response = await sendChatMessage(message);
      setMessages((current) => [
        ...current,
        { role: "void", content: response.response },
      ]);
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <h1>Chat</h1>
          <p>Send a message to the local Void agent.</p>
        </div>
      </div>

      <div className="messages">
        {messages.length === 0 ? (
          <EmptyState>No messages yet.</EmptyState>
        ) : (
          messages.map((message, index) => (
            <article className={`message ${message.role}`} key={index}>
              <div className="messageRole">
                {message.role === "user" ? "You" : "Void"}
              </div>
              <div className="messageContent">{message.content}</div>
            </article>
          ))
        )}
      </div>

      {error ? <div className="error">{error}</div> : null}

      <div className="composer">
        <textarea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
              void handleSend();
            }
          }}
          placeholder="Сделай статистику проекта"
          rows={4}
        />
        <button type="button" onClick={handleSend} disabled={loading}>
          {loading ? "Sending..." : "Send"}
        </button>
      </div>
    </section>
  );
}

function ApprovalsTab() {
  const [approvals, setApprovals] = useState<Approval[]>([]);
  const [loading, setLoading] = useState(true);
  const [actionId, setActionId] = useState("");
  const [error, setError] = useState("");

  async function loadApprovals() {
    try {
      setError("");
      setLoading(true);
      const response = await getApprovals();
      setApprovals(response.pending);
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setLoading(false);
    }
  }

  async function handleAction(id: string, action: "approve" | "reject") {
    setActionId(id);
    setError("");
    try {
      if (action === "approve") {
        await approve(id);
      } else {
        await reject(id);
      }
      await loadApprovals();
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setActionId("");
    }
  }

  useEffect(() => {
    void loadApprovals();
  }, []);

  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <h1>Approvals</h1>
          <p>Pending state-changing actions waiting for confirmation.</p>
        </div>
        <button className="secondaryButton" type="button" onClick={loadApprovals}>
          Refresh
        </button>
      </div>

      {error ? <div className="error">{error}</div> : null}
      {loading ? <EmptyState>Loading approvals...</EmptyState> : null}
      {!loading && approvals.length === 0 ? (
        <EmptyState>No pending approvals.</EmptyState>
      ) : null}

      <div className="cardGrid">
        {approvals.map((approval) => {
          const id = approval.id ?? "";
          return (
            <article className="card" key={id || approval.action}>
              <div className="cardTopline">
                <span>{id || "unknown id"}</span>
                <span>{approval.created_at}</span>
              </div>
              <h2>{approval.action ?? "Unknown action"}</h2>
              {approval.reason ? <p>{approval.reason}</p> : null}
              <JsonBlock value={approval.arguments ?? {}} />
              <div className="buttonRow">
                <button
                  type="button"
                  disabled={!id || actionId === id}
                  onClick={() => void handleAction(id, "approve")}
                >
                  Approve
                </button>
                <button
                  className="dangerButton"
                  type="button"
                  disabled={!id || actionId === id}
                  onClick={() => void handleAction(id, "reject")}
                >
                  Reject
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function TasksTab() {
  const [tasks, setTasks] = useState<ScheduledTask[]>([]);
  const [schedulerStatus, setSchedulerStatus] =
    useState<SchedulerStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [statusLoading, setStatusLoading] = useState(true);
  const [runDueLoading, setRunDueLoading] = useState(false);
  const [actionId, setActionId] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [scheduleType, setScheduleType] =
    useState<"once" | "interval" | "daily">("once");
  const [runAt, setRunAt] = useState("");
  const [minutes, setMinutes] = useState("60");
  const [time, setTime] = useState("09:00");

  async function loadTasks() {
    try {
      setError("");
      setLoading(true);
      const response = await getTasks();
      setTasks(response.tasks);
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setLoading(false);
    }
  }

  async function loadSchedulerStatus() {
    try {
      setError("");
      setStatusLoading(true);
      setSchedulerStatus(await getSchedulerStatus());
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setStatusLoading(false);
    }
  }

  async function handleRunDueTasks() {
    setError("");
    setMessage("");
    setRunDueLoading(true);
    try {
      const response = await runDueTasksNow();
      const count = response.results.length;
      setMessage(
        count === 0
          ? "No due tasks."
          : `Run due tasks completed: ${count} task${count === 1 ? "" : "s"}.`,
      );
      await Promise.all([loadTasks(), loadSchedulerStatus()]);
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setRunDueLoading(false);
    }
  }

  async function handleTaskAction(
    id: string,
    action: "run" | "enable" | "disable" | "delete",
  ) {
    setActionId(id);
    setError("");
    setMessage("");
    try {
      const response =
        action === "run"
          ? await runTask(id)
          : action === "enable"
            ? await enableTask(id)
            : action === "disable"
              ? await disableTask(id)
              : await deleteTask(id);
      setMessage(response.message);
      await loadTasks();
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setActionId("");
    }
  }

  async function handleCreate() {
    const cleanTitle = title.trim();
    const cleanPrompt = prompt.trim();
    if (!cleanTitle || !cleanPrompt) {
      setError("Title and prompt are required.");
      return;
    }

    const scheduleValue =
      scheduleType === "once"
        ? { run_at: runAt }
        : scheduleType === "interval"
          ? { minutes: Number(minutes) }
          : { time };

    setError("");
    setMessage("");
    try {
      const response = await createTask({
        title: cleanTitle,
        prompt: cleanPrompt,
        schedule_type: scheduleType,
        schedule_value: scheduleValue,
      });
      setMessage(response.message);
      setTitle("");
      setPrompt("");
      await loadTasks();
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    }
  }

  useEffect(() => {
    void Promise.all([loadTasks(), loadSchedulerStatus()]);
  }, []);

  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <h1>Tasks</h1>
          <p>Scheduled tasks stored in local memory.</p>
        </div>
        <button className="secondaryButton" type="button" onClick={loadTasks}>
          Refresh
        </button>
      </div>

      {error ? <div className="error">{error}</div> : null}
      {message ? <div className="notice">{message}</div> : null}

      <section className="schedulerPanel">
        <div>
          <div className="sectionLabel">Scheduler status</div>
          <div
            className={
              schedulerStatus?.enabled && schedulerStatus.running
                ? "status ok"
                : "status bad"
            }
          >
            <span className="statusDot" />
            {statusLoading
              ? "loading"
              : schedulerStatus?.enabled
                ? schedulerStatus.running
                  ? "running"
                  : "stopped"
                : "disabled"}
          </div>
          <div className="muted">
            Interval: {schedulerStatus?.interval_seconds ?? 60}s
          </div>
        </div>
        <div className="buttonRow schedulerActions">
          <button
            className="secondaryButton"
            type="button"
            onClick={() => void loadSchedulerStatus()}
            disabled={statusLoading}
          >
            Refresh status
          </button>
          <button
            type="button"
            onClick={() => void handleRunDueTasks()}
            disabled={runDueLoading}
          >
            {runDueLoading ? "Running..." : "Run due tasks now"}
          </button>
        </div>
      </section>

      <section className="taskForm">
        <h2>Create task</h2>
        <div className="formGrid">
          <label>
            <span>Title</span>
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="Check project"
            />
          </label>
          <label>
            <span>Schedule type</span>
            <select
              value={scheduleType}
              onChange={(event) =>
                setScheduleType(event.target.value as "once" | "interval" | "daily")
              }
            >
              <option value="once">once</option>
              <option value="interval">interval</option>
              <option value="daily">daily</option>
            </select>
          </label>
          {scheduleType === "once" ? (
            <label>
              <span>Run at</span>
              <input
                type="datetime-local"
                value={runAt}
                onChange={(event) => setRunAt(event.target.value)}
              />
            </label>
          ) : null}
          {scheduleType === "interval" ? (
            <label>
              <span>Minutes</span>
              <input
                min="1"
                type="number"
                value={minutes}
                onChange={(event) => setMinutes(event.target.value)}
              />
            </label>
          ) : null}
          {scheduleType === "daily" ? (
            <label>
              <span>Time</span>
              <input
                type="time"
                value={time}
                onChange={(event) => setTime(event.target.value)}
              />
            </label>
          ) : null}
        </div>
        <label>
          <span>Prompt</span>
          <textarea
            value={prompt}
            onChange={(event) => setPrompt(event.target.value)}
            placeholder="Проверь состояние проекта и покажи краткий отчёт"
            rows={4}
          />
        </label>
        <button type="button" onClick={handleCreate}>
          Create
        </button>
      </section>

      {loading ? <EmptyState>Loading tasks...</EmptyState> : null}
      {!loading && tasks.length === 0 ? <EmptyState>No scheduled tasks.</EmptyState> : null}

      <div className="cardGrid">
        {tasks.map((task) => {
          const id = task.id ?? "";
          return (
            <article className="card" key={id || task.title}>
              <div className="cardTopline">
                <span>{id || "unknown id"}</span>
                <span>{task.enabled ? "enabled" : "disabled"}</span>
              </div>
              <h2>{task.title ?? "Untitled task"}</h2>
              <div className="field">
                <span>Schedule</span>
                <p>{task.schedule_type ?? "unknown"}</p>
              </div>
              <div className="field">
                <span>Next run</span>
                <p>{task.next_run_at ?? "none"}</p>
              </div>
              <div className="field">
                <span>Last run</span>
                <p>{task.last_run_at ?? "never"}</p>
              </div>
              <div className="buttonRow">
                <button
                  type="button"
                  disabled={!id || actionId === id}
                  onClick={() => void handleTaskAction(id, "run")}
                >
                  Run
                </button>
                {task.enabled ? (
                  <button
                    className="secondaryButton"
                    type="button"
                    disabled={!id || actionId === id}
                    onClick={() => void handleTaskAction(id, "disable")}
                  >
                    Disable
                  </button>
                ) : (
                  <button
                    className="secondaryButton"
                    type="button"
                    disabled={!id || actionId === id}
                    onClick={() => void handleTaskAction(id, "enable")}
                  >
                    Enable
                  </button>
                )}
                <button
                  className="dangerButton"
                  type="button"
                  disabled={!id || actionId === id}
                  onClick={() => void handleTaskAction(id, "delete")}
                >
                  Delete
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}

function CapabilityCard({ capability }: { capability: Capability }) {
  const detail =
    capability.description ?? capability.problem ?? capability.reason ?? "";

  return (
    <article className="card">
      <div className="cardTopline">
        <span>{capability.status ?? "unknown"}</span>
        <span>{capability.updated_at ?? capability.created_at}</span>
      </div>
      <h2>{capability.name ?? "Unnamed capability"}</h2>
      {detail ? <p>{detail}</p> : null}
      {capability.problem ? (
        <div className="field">
          <span>Problem</span>
          <p>{capability.problem}</p>
        </div>
      ) : null}
      {capability.reason ? (
        <div className="field">
          <span>Reason</span>
          <p>{capability.reason}</p>
        </div>
      ) : null}
    </article>
  );
}

function CapabilitySection({
  title,
  capabilities,
}: {
  title: string;
  capabilities: Capability[];
}) {
  return (
    <section className="contentSection">
      <h2>{title}</h2>
      {capabilities.length === 0 ? (
        <EmptyState>No records.</EmptyState>
      ) : (
        <div className="cardGrid">
          {capabilities.map((capability, index) => (
            <CapabilityCard
              capability={capability}
              key={capability.id ?? capability.name ?? index}
            />
          ))}
        </div>
      )}
    </section>
  );
}

function CapabilitiesTab() {
  const [capabilities, setCapabilities] = useState({
    installed: [] as Capability[],
    requested: [] as Capability[],
    rejected: [] as Capability[],
  });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadCapabilities() {
    try {
      setError("");
      setLoading(true);
      const response = await getCapabilities();
      setCapabilities({
        installed: response.installed,
        requested: response.requested,
        rejected: response.rejected,
      });
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadCapabilities();
  }, []);

  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <h1>Capabilities</h1>
          <p>Installed, requested, and rejected capability records.</p>
        </div>
        <button
          className="secondaryButton"
          type="button"
          onClick={loadCapabilities}
        >
          Refresh
        </button>
      </div>
      {error ? <div className="error">{error}</div> : null}
      {loading ? <EmptyState>Loading capabilities...</EmptyState> : null}
      {!loading ? (
        <>
          <CapabilitySection
            title="Installed"
            capabilities={capabilities.installed}
          />
          <CapabilitySection
            title="Requested"
            capabilities={capabilities.requested}
          />
          <CapabilitySection title="Rejected" capabilities={capabilities.rejected} />
        </>
      ) : null}
    </section>
  );
}

function SkillsTab() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadSkills() {
    try {
      setError("");
      setLoading(true);
      const response = await getSkills();
      setSkills(response.skills);
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadSkills();
  }, []);

  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <h1>Skills</h1>
          <p>Registered deterministic skills available to Void.</p>
        </div>
        <button className="secondaryButton" type="button" onClick={loadSkills}>
          Refresh
        </button>
      </div>
      {error ? <div className="error">{error}</div> : null}
      {loading ? <EmptyState>Loading skills...</EmptyState> : null}
      {!loading && skills.length === 0 ? <EmptyState>No skills.</EmptyState> : null}
      <div className="cardGrid">
        {skills.map((skill, index) => (
          <article className="card" key={skill.name ?? index}>
            <h2>{skill.name ?? "Unnamed skill"}</h2>
            {skill.description ? <p>{skill.description}</p> : null}
            {skill.keywords?.length ? (
              <div className="tags">
                {skill.keywords.map((keyword) => (
                  <span key={keyword}>{keyword}</span>
                ))}
              </div>
            ) : null}
          </article>
        ))}
      </div>
    </section>
  );
}

function MemoryBlock({
  title,
  memory,
  onRefresh,
}: {
  title: string;
  memory: MemoryResponse | null;
  onRefresh: () => void;
}) {
  return (
    <section className="memoryBlock">
      <div className="memoryHeader">
        <h2>{title}</h2>
        <button className="secondaryButton" type="button" onClick={onRefresh}>
          Refresh
        </button>
      </div>
      <pre className="memoryContent">
        <code>{memory?.content || "No content."}</code>
      </pre>
    </section>
  );
}

function MemoryTab() {
  const [project, setProject] = useState<MemoryResponse | null>(null);
  const [facts, setFacts] = useState<MemoryResponse | null>(null);
  const [session, setSession] = useState<MemoryResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadProject() {
    setProject(await getProjectMemory());
  }

  async function loadFacts() {
    setFacts(await getFactsMemory());
  }

  async function loadSession() {
    setSession(await getSessionMemory());
  }

  async function loadAll() {
    try {
      setError("");
      setLoading(true);
      const [projectMemory, factsMemory, sessionMemory] = await Promise.all([
        getProjectMemory(),
        getFactsMemory(),
        getSessionMemory(),
      ]);
      setProject(projectMemory);
      setFacts(factsMemory);
      setSession(sessionMemory);
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setLoading(false);
    }
  }

  async function refreshOne(loader: () => Promise<void>) {
    try {
      setError("");
      await loader();
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    }
  }

  useEffect(() => {
    void loadAll();
  }, []);

  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <h1>Memory</h1>
          <p>Project, facts, and session memory files.</p>
        </div>
        <button className="secondaryButton" type="button" onClick={loadAll}>
          Refresh all
        </button>
      </div>
      {error ? <div className="error">{error}</div> : null}
      {loading ? <EmptyState>Loading memory...</EmptyState> : null}
      {!loading ? (
        <div className="memoryGrid">
          <MemoryBlock
            title="Project memory"
            memory={project}
            onRefresh={() => void refreshOne(loadProject)}
          />
          <MemoryBlock
            title="Facts memory"
            memory={facts}
            onRefresh={() => void refreshOne(loadFacts)}
          />
          <MemoryBlock
            title="Session memory"
            memory={session}
            onRefresh={() => void refreshOne(loadSession)}
          />
        </div>
      ) : null}
    </section>
  );
}

function ActiveTab({ tab }: { tab: Tab }) {
  if (tab === "approvals") {
    return <ApprovalsTab />;
  }
  if (tab === "tasks") {
    return <TasksTab />;
  }
  if (tab === "capabilities") {
    return <CapabilitiesTab />;
  }
  if (tab === "skills") {
    return <SkillsTab />;
  }
  if (tab === "memory") {
    return <MemoryTab />;
  }
  return <ChatTab />;
}

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("chat");

  return (
    <div className="appShell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brandMark">V</div>
          <div>
            <div className="brandName">Void</div>
            <div className="brandMeta">Local Web UI</div>
          </div>
        </div>
        <StatusPanel />
        <AuthPanel />
        <nav className="nav">
          {tabs.map((tab) => (
            <button
              className={activeTab === tab.id ? "active" : ""}
              type="button"
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </nav>
      </aside>
      <main className="main">
        <ActiveTab tab={activeTab} />
      </main>
    </div>
  );
}
