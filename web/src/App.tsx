import { useEffect, useState } from "react";
import {
  Activity,
  Approval,
  BrowserSession,
  Capability,
  ClarificationRequest,
  HealthResponse,
  MemoryResponse,
  Project,
  ProjectBackup,
  ProjectBackupPreview,
  ProjectImportPreview,
  SchedulerStatusResponse,
  ScheduledTask,
  Skill,
  approve,
  clearActivityHistory,
  clickBrowserSession,
  clickBrowserSelector,
  clearStoredToken,
  closeAllBrowserSessions,
  closeBrowserSession,
  createProjectBackup,
  createProject,
  createGitCommit,
  createTask,
  deleteProjectBackup,
  deleteProject,
  deleteTask,
  describeCurrentProject,
  disableTask,
  duplicateProject,
  enableTask,
  exportAllProjects,
  exportCurrentProject,
  exportProject,
  extractBrowserText,
  fillBrowserSession,
  fillBrowserSelector,
  getActivity,
  getApprovals,
  getBrowserLinks,
  getBrowserScreenshot,
  getBrowserSessionStatus,
  getBrowserTitle,
  getClarification,
  getCapabilities,
  getFactsMemory,
  getGitBranch,
  getGitDiff,
  getGitLog,
  getGitStagedDiff,
  getGitStatus,
  getProjectCommands,
  getProjectMemory,
  getProjects,
  getSchedulerStatus,
  getSessionMemory,
  getSkills,
  getTasks,
  getStoredToken,
  getWorkspacePreferences,
  health,
  importProjects,
  listProjectBackups,
  listBrowserSessions,
  openBrowserSession,
  openProjectRepo,
  openProjectWorkspace,
  reject,
  replayActivity,
  restoreProjectBackup,
  respondToClarification,
  runBrowserTask,
  runDueTasksNow,
  runProjectCommand,
  runProjectCommandVisible,
  runTask,
  sendChatMessage,
  setCurrentProject,
  setStoredToken,
  submitBrowserSession,
  submitBrowserSelector,
  updateProject,
  suggestGitCommitMessage,
  updateWorkspacePreferences,
  validateProjectImport,
  validateProjectBackup,
  waitForBrowserSession,
  waitForBrowserSelector,
} from "./api";
import {
  backupPreviewStatus,
  emptyProjectEditorState,
  emptyWorkspacePreferenceForm,
  formatBackupSize,
  formatProjectExport,
  importPreviewAliasOwnershipChanges,
  importPreviewAliasRenames,
  importPreviewStatus,
  parseProjectImportJson,
  projectEditorForRefresh,
  projectEditorFromProject,
  projectPayloadFromEditor,
  workspaceFormFromPreferences,
} from "./projectRegistry";
import type {
  ProjectEditorRefreshOptions,
  ProjectEditorState,
  WorkspacePreferenceForm,
} from "./projectRegistry";

type Tab =
  | "chat"
  | "browser"
  | "git"
  | "project"
  | "approvals"
  | "tasks"
  | "capabilities"
  | "skills"
  | "activity"
  | "memory";

type Message = {
  role: "user" | "void";
  content: string;
  resultType?: string;
  data?: Record<string, unknown> | null;
};

type ApprovalAction = "approve" | "reject";

type StructuredResult = {
  message: string;
  resultType?: string;
  data?: Record<string, unknown> | null;
};

const tabs: { id: Tab; label: string }[] = [
  { id: "chat", label: "Chat" },
  { id: "browser", label: "Browser" },
  { id: "git", label: "Git" },
  { id: "project", label: "Projects" },
  { id: "approvals", label: "Approvals" },
  { id: "tasks", label: "Tasks" },
  { id: "capabilities", label: "Capabilities" },
  { id: "skills", label: "Skills" },
  { id: "activity", label: "Activity" },
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

function approvalTimestamp(approval: Approval) {
  const time = approval.created_at ? Date.parse(approval.created_at) : Number.NaN;
  return Number.isFinite(time) ? time : 0;
}

function newestApproval(
  approvals: Approval[],
  predicate: (approval: Approval) => boolean = () => true,
) {
  return approvals.reduce<Approval | null>((newest, approval) => {
    if (!approval.id || !predicate(approval)) {
      return newest;
    }
    if (!newest) {
      return approval;
    }
    return approvalTimestamp(approval) >= approvalTimestamp(newest) ? approval : newest;
  }, null);
}

async function fetchInlineApproval(predicate?: (approval: Approval) => boolean) {
  const response = await getApprovals();
  return newestApproval(response.pending, predicate);
}

async function resolveInlineApproval(id: string, action: ApprovalAction) {
  return action === "approve" ? approve(id) : reject(id);
}

function mentionsApproval(message: string) {
  return message.toLowerCase().includes("approval");
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null
    ? (value as Record<string, unknown>)
    : null;
}

function asText(value: unknown, fallback = "") {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function responseResultType(response: {
  result_type?: string;
  data?: Record<string, unknown> | null;
}) {
  const data = response.data ?? {};
  if ("approval_id" in data) {
    return "approval";
  }
  if (response.result_type === "terminal_launch_result") {
    return "terminal_launch_result";
  }
  if ("command_key" in data) {
    return "command_result";
  }
  if ("session_id" in data && "url" in data) {
    return "browser_result";
  }
  if (response.result_type === "clarification_request") {
    return "clarification";
  }
  return response.result_type ?? "message";
}

function toStructuredResult(response: {
  message?: string;
  response?: string;
  result_type?: string;
  data?: Record<string, unknown> | null;
}): StructuredResult {
  return {
    message: response.message ?? response.response ?? "",
    resultType: responseResultType(response),
    data: response.data,
  };
}

function FieldList({ fields }: { fields: Array<[string, unknown]> }) {
  return (
    <dl className="resultFields">
      {fields.map(([label, value]) => (
        <div className="resultField" key={label}>
          <dt>{label}</dt>
          <dd>{value === null || value === undefined || value === "" ? "none" : String(value)}</dd>
        </div>
      ))}
    </dl>
  );
}

function ResultBlock({ result }: { result: StructuredResult }) {
  const data = result.data ?? {};
  const project = asRecord(data.project);
  const session = asRecord(data.session);
  const terminal = asRecord(data.terminal);
  const type = result.resultType ?? "message";

  if (type === "approval") {
    return (
      <article className="resultBlock approvalResult">
        <div className="cardTopline">
          <span>Approval required</span>
          <span>{asText(data.approval_id, "pending")}</span>
        </div>
        <p>{result.message}</p>
        <FieldList
          fields={[
            ["Action", data.action],
            ["Category", data.category],
            ["Risk", data.risk_level],
          ]}
        />
      </article>
    );
  }

  if (type === "command_result") {
    return (
      <article className="resultBlock commandResultBlock">
        <div className="cardTopline">
          <span>Command result</span>
          <span>{data.ok === false ? "failed" : "complete"}</span>
        </div>
        <FieldList
          fields={[
            ["Command key", data.command_key],
            ["Command", data.command],
            ["CWD", data.cwd],
            ["Return code", data.returncode],
            ["Duration", `${data.duration_seconds ?? "unknown"}s`],
          ]}
        />
        <div className="resultOutputGrid">
          <div>
            <div className="sectionLabel">stdout</div>
            <pre className="resultOutput">{asText(data.stdout, "(empty)")}</pre>
          </div>
          <div>
            <div className="sectionLabel">stderr</div>
            <pre className="resultOutput">{asText(data.stderr, "(empty)")}</pre>
          </div>
        </div>
      </article>
    );
  }

  if (type === "terminal_launch_result") {
    return (
      <article className="resultBlock terminalResultBlock">
        <div className="cardTopline">
          <span>Terminal launch</span>
          <span>{terminal?.ok === false ? "failed" : "launched"}</span>
        </div>
        <FieldList
          fields={[
            ["Command key", data.command_key],
            ["Command", data.command],
            ["CWD", data.cwd],
            ["Project", project?.name],
            ["Terminal app", terminal?.app],
            ["Terminal type", terminal?.terminal_type],
            ["Workspace action", terminal?.action],
            ["Session id", terminal?.session_id],
            ["Window id", terminal?.window_id],
            ["Tab id", terminal?.tab_id],
            ["PID", terminal?.pid],
            ["Status", terminal?.ok === false ? "failed" : "launched"],
            ["Message", terminal?.message],
            ["Mode", data.mode ?? "visible_terminal"],
          ]}
        />
      </article>
    );
  }

  if (type === "browser_result") {
    return (
      <article className="resultBlock browserResultBlock">
        <div className="cardTopline">
          <span>Browser session</span>
          <span>{asText(data.session_id ?? session?.session_id, "opened")}</span>
        </div>
        <FieldList
          fields={[
            ["Project", project?.name],
            ["Repo URL", data.url ?? session?.url],
            ["Session ID", data.session_id ?? session?.session_id],
            ["Mode", data.mode ?? session?.mode],
            ["Title", data.title ?? session?.title],
          ]}
        />
      </article>
    );
  }

  return <div className="notice">{result.message}</div>;
}

function InlineApprovalCard({
  approval,
  resolving,
  onResolve,
}: {
  approval: Approval;
  resolving: boolean;
  onResolve: (id: string, action: ApprovalAction) => void;
}) {
  const id = approval.id ?? "";

  return (
    <article className="inlineApprovalCard">
      <div className="cardTopline">
        <span>{id || "unknown id"}</span>
        <span>{approval.created_at}</span>
      </div>
      <h2>{approval.action ?? "Unknown action"}</h2>
      {approval.category || approval.risk_level ? (
        <p>{[approval.category, approval.risk_level].filter(Boolean).join(" / ")}</p>
      ) : null}
      {approval.reason ? <p>{approval.reason}</p> : null}
      <JsonBlock value={approval.arguments ?? {}} />
      <div className="buttonRow">
        <button
          type="button"
          disabled={!id || resolving}
          onClick={() => onResolve(id, "approve")}
        >
          {resolving ? "Working..." : "Approve"}
        </button>
        <button
          className="dangerButton"
          type="button"
          disabled={!id || resolving}
          onClick={() => onResolve(id, "reject")}
        >
          Reject
        </button>
      </div>
    </article>
  );
}

function normalizeClarification(raw: unknown): ClarificationRequest | null {
  if (typeof raw !== "object" || raw === null) {
    return null;
  }
  const payload = raw as Record<string, unknown>;
  const question = payload.question;
  const type = payload.type ?? payload.clarification_type;
  if (typeof question !== "string" || typeof type !== "string") {
    return null;
  }
  const context =
    typeof payload.context === "object" && payload.context !== null
      ? (payload.context as Record<string, unknown>)
      : {};
  return {
    id: typeof payload.id === "string" ? payload.id : null,
    question,
    clarification_type: type,
    context,
  };
}

function InlineClarificationCard({
  clarification,
  answer,
  submitting,
  onAnswerChange,
  onSubmit,
}: {
  clarification: ClarificationRequest;
  answer: string;
  submitting: boolean;
  onAnswerChange: (answer: string) => void;
  onSubmit: () => void;
}) {
  const commands = Array.isArray(clarification.context.available_commands)
    ? clarification.context.available_commands
        .filter((value): value is string => typeof value === "string" && Boolean(value))
    : [];
  const projects = Array.isArray(clarification.context.available_projects)
    ? clarification.context.available_projects
        .filter((value): value is string => typeof value === "string" && Boolean(value))
    : [];
  const suggestions = commands.length > 0 ? commands : projects;
  const suggestionLabel = commands.length > 0 ? "Available commands" : "Available projects";

  return (
    <article className="inlineClarificationCard">
      <div className="cardTopline">
        <span>{clarification.id || "clarification"}</span>
        <span>{clarification.clarification_type}</span>
      </div>
      <h2>{clarification.question}</h2>
      {suggestions.length > 0 ? (
        <div className="clarificationSuggestions">
          <div className="sectionLabel">{suggestionLabel}</div>
          <div className="chipRow">
            {suggestions.map((suggestion) => (
              <button
                className="chipButton"
                type="button"
                key={suggestion}
                disabled={submitting}
                onClick={() => onAnswerChange(suggestion)}
              >
                {suggestion}
              </button>
            ))}
          </div>
        </div>
      ) : null}
      <div className="clarificationComposer">
        <input
          value={answer}
          onChange={(event) => onAnswerChange(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              onSubmit();
            }
          }}
          placeholder="Void"
        />
        <button type="button" disabled={submitting || !answer.trim()} onClick={onSubmit}>
          {submitting ? "Submitting..." : "Submit"}
        </button>
      </div>
    </article>
  );
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
  const [inlineApproval, setInlineApproval] = useState<Approval | null>(null);
  const [inlineClarification, setInlineClarification] =
    useState<ClarificationRequest | null>(null);
  const [clarificationAnswer, setClarificationAnswer] = useState("");
  const [approvalActionId, setApprovalActionId] = useState("");
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
    setInlineClarification(null);

    try {
      const response = await sendChatMessage(message);
      setMessages((current) => [
        ...current,
        {
          role: "void",
          content: response.response,
          resultType: responseResultType(response),
          data: response.data,
        },
      ]);
      if (response.result_type === "clarification_request" && response.clarification) {
        setInlineClarification(response.clarification);
        setClarificationAnswer("");
      }
      if (responseResultType(response) === "approval" || mentionsApproval(response.response)) {
        const approvalId = asText(response.data?.approval_id);
        const pendingApproval = await fetchInlineApproval(
          approvalId ? (approval) => approval.id === approvalId : undefined,
        );
        setInlineApproval(pendingApproval);
      }
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setLoading(false);
    }
  }

  async function handleClarificationSubmit() {
    const answer = clarificationAnswer.trim();
    if (!answer || loading) {
      return;
    }

    setError("");
    setLoading(true);
    setMessages((current) => [...current, { role: "user", content: answer }]);
    try {
      const response = await respondToClarification({ answer });
      setMessages((current) => [
        ...current,
        {
          role: "void",
          content: response.response,
          resultType: responseResultType(response),
          data: response.data,
        },
      ]);
      setInlineClarification(
        response.result_type === "clarification_request" && response.clarification
          ? response.clarification
          : null,
      );
      setClarificationAnswer("");
      if (responseResultType(response) === "approval" || mentionsApproval(response.response)) {
        const approvalId = asText(response.data?.approval_id);
        const pendingApproval = await fetchInlineApproval(
          approvalId ? (approval) => approval.id === approvalId : undefined,
        );
        setInlineApproval(pendingApproval);
      }
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setLoading(false);
    }
  }

  async function handleApprovalAction(id: string, action: ApprovalAction) {
    setApprovalActionId(id);
    setError("");
    try {
      const response = await resolveInlineApproval(id, action);
      const result = toStructuredResult(response);
      setMessages((current) => [
        ...current,
        {
          role: "void",
          content: response.message,
          resultType: result.resultType,
          data: result.data,
        },
      ]);
      setInlineApproval(null);
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setApprovalActionId("");
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
              {message.role === "void" && message.resultType ? (
                <ResultBlock
                  result={{
                    message: message.content,
                    resultType: message.resultType,
                    data: message.data,
                  }}
                />
              ) : (
                <div className="messageContent">{message.content}</div>
              )}
            </article>
          ))
        )}
      </div>

      {inlineApproval ? (
        <InlineApprovalCard
          approval={inlineApproval}
          resolving={approvalActionId === inlineApproval.id}
          onResolve={handleApprovalAction}
        />
      ) : null}
      {inlineClarification ? (
        <InlineClarificationCard
          clarification={inlineClarification}
          answer={clarificationAnswer}
          submitting={loading}
          onAnswerChange={setClarificationAnswer}
          onSubmit={() => void handleClarificationSubmit()}
        />
      ) : null}

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

function BrowserTab() {
  const [url, setUrl] = useState("https://example.com");
  const [sessionMode, setSessionMode] = useState<"headless" | "visible">("headless");
  const [sessions, setSessions] = useState<BrowserSession[]>([]);
  const [selector, setSelector] = useState("#login");
  const [value, setValue] = useState("test@test.com");
  const [timeoutMs, setTimeoutMs] = useState("10000");
  const [instruction, setInstruction] = useState("Изучи страницу кратко");
  const [loadingAction, setLoadingAction] = useState("");
  const [inlineApproval, setInlineApproval] = useState<Approval | null>(null);
  const [approvalActionId, setApprovalActionId] = useState("");
  const [result, setResult] = useState<StructuredResult | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    void refreshSessions();
    void loadBrowserApproval();
  }, []);

  async function loadBrowserApproval() {
    const pendingApproval = await fetchInlineApproval(
      (approval) => approval.category === "browser",
    );
    setInlineApproval(pendingApproval);
  }

  async function refreshSessions() {
    try {
      const response = await listBrowserSessions();
      setSessions(response.sessions);
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    }
  }

  async function refreshBrowserState() {
    await refreshSessions();
    await loadBrowserApproval();
  }

  async function handleBrowserAction(action: string) {
    const cleanUrl = url.trim();
    if (!cleanUrl) {
      setError("URL is required.");
      return;
    }

    setError("");
    setResult(null);
    setInlineApproval(null);
    setLoadingAction(action);
    try {
      const response =
        action === "title"
          ? await getBrowserTitle(cleanUrl)
          : action === "text"
            ? await extractBrowserText(cleanUrl)
            : action === "links"
              ? await getBrowserLinks(cleanUrl)
              : action === "screenshot"
                ? await getBrowserScreenshot(cleanUrl)
                : await runBrowserTask({
                    url: cleanUrl,
                    instruction: instruction.trim() || "Read-only page inspection.",
                  });
      setResult(toStructuredResult(response));
      await loadBrowserApproval();
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setLoadingAction("");
    }
  }

  async function handleInteractiveAction(action: string) {
    const cleanUrl = url.trim();
    const cleanSelector = selector.trim();
    const cleanValue = value;
    const parsedTimeout = Number(timeoutMs);

    if (!cleanUrl) {
      setError("URL is required.");
      return;
    }
    if (!cleanSelector) {
      setError("Selector is required.");
      return;
    }
    if (action === "wait" && (!Number.isFinite(parsedTimeout) || parsedTimeout < 1)) {
      setError("Timeout must be greater than 0.");
      return;
    }

    setError("");
    setResult(null);
    setInlineApproval(null);
    setLoadingAction(action);
    try {
      const response =
        action === "click"
          ? await clickBrowserSelector({ url: cleanUrl, selector: cleanSelector })
          : action === "fill"
            ? await fillBrowserSelector({
                url: cleanUrl,
                selector: cleanSelector,
                value: cleanValue,
              })
            : action === "submit"
              ? await submitBrowserSelector({
                  url: cleanUrl,
                  selector: cleanSelector,
                })
              : await waitForBrowserSelector({
                  url: cleanUrl,
                  selector: cleanSelector,
                  timeout_ms: parsedTimeout,
                });
      setResult(toStructuredResult(response));
      await loadBrowserApproval();
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setLoadingAction("");
    }
  }

  async function handleOpenSession() {
    const cleanUrl = url.trim();
    if (!cleanUrl) {
      setError("URL is required.");
      return;
    }

    setError("");
    setResult(null);
    setInlineApproval(null);
    setLoadingAction("open-session");
    try {
      const response = await openBrowserSession({
        url: cleanUrl,
        mode: sessionMode,
      });
      setResult(toStructuredResult(response));
      await loadBrowserApproval();
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setLoadingAction("");
    }
  }

  async function handleSessionStatus(id: string) {
    setError("");
    setResult(null);
    setLoadingAction(`status-${id}`);
    try {
      const response = await getBrowserSessionStatus(id);
      setResult({
        message: "Browser session status.",
        resultType: "browser_result",
        data: { session: response.session },
      });
      await refreshSessions();
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setLoadingAction("");
    }
  }

  async function handleCloseSession(id: string) {
    setError("");
    setResult(null);
    setInlineApproval(null);
    setLoadingAction(`close-${id}`);
    try {
      const response = await closeBrowserSession(id);
      setResult(toStructuredResult(response));
      await loadBrowserApproval();
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setLoadingAction("");
    }
  }

  async function handleCloseAllSessions() {
    setError("");
    setResult(null);
    setInlineApproval(null);
    setLoadingAction("close-all-sessions");
    try {
      const response = await closeAllBrowserSessions();
      setResult(toStructuredResult(response));
      await loadBrowserApproval();
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setLoadingAction("");
    }
  }

  async function handleSessionAction(id: string, action: string) {
    const cleanSelector = selector.trim();
    const parsedTimeout = Number(timeoutMs);

    if (!cleanSelector) {
      setError("Selector is required.");
      return;
    }
    if (action === "wait" && (!Number.isFinite(parsedTimeout) || parsedTimeout < 1)) {
      setError("Timeout must be greater than 0.");
      return;
    }

    setError("");
    setResult(null);
    setInlineApproval(null);
    setLoadingAction(`${action}-${id}`);
    try {
      const response =
        action === "click"
          ? await clickBrowserSession(id, { selector: cleanSelector })
          : action === "fill"
            ? await fillBrowserSession(id, {
                selector: cleanSelector,
                value,
              })
            : action === "submit"
              ? await submitBrowserSession(id, { selector: cleanSelector })
              : await waitForBrowserSession(id, {
                  selector: cleanSelector,
                  timeout_ms: parsedTimeout,
                });
      setResult(toStructuredResult(response));
      await loadBrowserApproval();
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setLoadingAction("");
    }
  }

  async function handleApprovalAction(id: string, action: ApprovalAction) {
    setApprovalActionId(id);
    setError("");
    try {
      const response = await resolveInlineApproval(id, action);
      setResult(toStructuredResult(response));
      await refreshBrowserState();
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setApprovalActionId("");
    }
  }

  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <h1>Browser</h1>
          <p>Approval-gated Playwright actions for http/https pages.</p>
        </div>
      </div>

      {error ? <div className="error">{error}</div> : null}
      {result ? <ResultBlock result={result} /> : null}
      {inlineApproval ? (
        <InlineApprovalCard
          approval={inlineApproval}
          resolving={approvalActionId === inlineApproval.id}
          onResolve={handleApprovalAction}
        />
      ) : null}

      <section className="browserPanel">
        <label>
          <span>URL</span>
          <input
            value={url}
            onChange={(event) => setUrl(event.target.value)}
            placeholder="https://example.com"
          />
        </label>
        <label>
          <span>Session mode</span>
          <select
            value={sessionMode}
            onChange={(event) =>
              setSessionMode(event.target.value === "visible" ? "visible" : "headless")
            }
          >
            <option value="headless">headless</option>
            <option value="visible">visible</option>
          </select>
        </label>
        <label>
          <span>Browser task instruction</span>
          <textarea
            value={instruction}
            onChange={(event) => setInstruction(event.target.value)}
            rows={4}
            placeholder="Проверь сайт и покажи краткую сводку"
          />
        </label>
        <div className="browserInteractiveGrid">
          <label>
            <span>Selector</span>
            <input
              value={selector}
              onChange={(event) => setSelector(event.target.value)}
              placeholder="#login"
            />
          </label>
          <label>
            <span>Fill value</span>
            <input
              value={value}
              onChange={(event) => setValue(event.target.value)}
              placeholder="test@test.com"
            />
          </label>
          <label>
            <span>Wait timeout ms</span>
            <input
              inputMode="numeric"
              value={timeoutMs}
              onChange={(event) => setTimeoutMs(event.target.value)}
              placeholder="10000"
            />
          </label>
        </div>
        <div className="buttonRow">
          <button
            type="button"
            disabled={Boolean(loadingAction)}
            onClick={() => void handleBrowserAction("title")}
          >
            {loadingAction === "title" ? "Requesting..." : "Get title"}
          </button>
          <button
            type="button"
            disabled={Boolean(loadingAction)}
            onClick={() => void handleBrowserAction("text")}
          >
            {loadingAction === "text" ? "Requesting..." : "Extract text"}
          </button>
          <button
            type="button"
            disabled={Boolean(loadingAction)}
            onClick={() => void handleBrowserAction("links")}
          >
            {loadingAction === "links" ? "Requesting..." : "Links"}
          </button>
          <button
            type="button"
            disabled={Boolean(loadingAction)}
            onClick={() => void handleBrowserAction("screenshot")}
          >
            {loadingAction === "screenshot" ? "Requesting..." : "Screenshot"}
          </button>
          <button
            type="button"
            disabled={Boolean(loadingAction)}
            onClick={() => void handleBrowserAction("task")}
          >
            {loadingAction === "task" ? "Requesting..." : "Browser task"}
          </button>
        </div>
        <div className="buttonRow">
          <button
            type="button"
            disabled={Boolean(loadingAction)}
            onClick={() => void handleInteractiveAction("click")}
          >
            {loadingAction === "click" ? "Requesting..." : "Click"}
          </button>
          <button
            type="button"
            disabled={Boolean(loadingAction)}
            onClick={() => void handleInteractiveAction("fill")}
          >
            {loadingAction === "fill" ? "Requesting..." : "Fill"}
          </button>
          <button
            type="button"
            disabled={Boolean(loadingAction)}
            onClick={() => void handleInteractiveAction("submit")}
          >
            {loadingAction === "submit" ? "Requesting..." : "Submit"}
          </button>
          <button
            type="button"
            disabled={Boolean(loadingAction)}
            onClick={() => void handleInteractiveAction("wait")}
          >
            {loadingAction === "wait" ? "Requesting..." : "Wait"}
          </button>
        </div>
        <div className="muted">
          Stateless actions open a fresh background browser each time. Managed sessions
          keep the same browser page alive.
        </div>
        <div className="browserSessionHeader">
          <h2>Browser Sessions</h2>
          <div className="buttonRow">
            <button
              type="button"
              disabled={Boolean(loadingAction)}
              onClick={() => void handleOpenSession()}
            >
              {loadingAction === "open-session" ? "Requesting..." : "Open session"}
            </button>
            <button
              className="secondaryButton"
              type="button"
              disabled={Boolean(loadingAction)}
              onClick={() => void refreshSessions()}
            >
              Refresh sessions
            </button>
            <button
              className="dangerButton"
              type="button"
              disabled={Boolean(loadingAction)}
              onClick={() => void handleCloseAllSessions()}
            >
              {loadingAction === "close-all-sessions"
                ? "Requesting..."
                : "Close all sessions"}
            </button>
          </div>
        </div>
        <div className="muted">
          Visible sessions are opened by Void and are not attached to your personal
          browser. Attach-to-existing-browser is not implemented.
        </div>
        <div className="browserSessionsList">
          {sessions.length === 0 ? (
            <div className="empty">No browser sessions are open.</div>
          ) : (
            sessions.map((session) => {
              const id = session.session_id ?? "";
              return (
                <article className="browserSessionCard" key={id || session.url}>
                  <div className="cardTopline">
                    <span>{id || "unknown session"}</span>
                    <span>{session.mode}</span>
                  </div>
                  <h2>{session.title || "(no title)"}</h2>
                  <p>{session.url}</p>
                  <div className="browserSessionMeta">
                    <span>created {session.created_at || "unknown"}</span>
                    <span>last used {session.last_used_at || "unknown"}</span>
                  </div>
                  <div className="buttonRow">
                    <button
                      className="secondaryButton"
                      type="button"
                      disabled={!id || Boolean(loadingAction)}
                      onClick={() => void handleSessionStatus(id)}
                    >
                      {loadingAction === `status-${id}` ? "Loading..." : "Status"}
                    </button>
                    <button
                      className="dangerButton"
                      type="button"
                      disabled={!id || Boolean(loadingAction)}
                      onClick={() => void handleCloseSession(id)}
                    >
                      {loadingAction === `close-${id}` ? "Requesting..." : "Close"}
                    </button>
                    <button
                      type="button"
                      disabled={!id || Boolean(loadingAction)}
                      onClick={() => void handleSessionAction(id, "click")}
                    >
                      {loadingAction === `click-${id}` ? "Requesting..." : "Click"}
                    </button>
                    <button
                      type="button"
                      disabled={!id || Boolean(loadingAction)}
                      onClick={() => void handleSessionAction(id, "fill")}
                    >
                      {loadingAction === `fill-${id}` ? "Requesting..." : "Fill"}
                    </button>
                    <button
                      type="button"
                      disabled={!id || Boolean(loadingAction)}
                      onClick={() => void handleSessionAction(id, "submit")}
                    >
                      {loadingAction === `submit-${id}` ? "Requesting..." : "Submit"}
                    </button>
                    <button
                      type="button"
                      disabled={!id || Boolean(loadingAction)}
                      onClick={() => void handleSessionAction(id, "wait")}
                    >
                      {loadingAction === `wait-${id}` ? "Requesting..." : "Wait"}
                    </button>
                  </div>
                </article>
              );
            })
          )}
        </div>
      </section>
    </section>
  );
}

function GitTab() {
  const [commitMessage, setCommitMessage] = useState("");
  const [loadingAction, setLoadingAction] = useState("");
  const [result, setResult] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");

  async function handleGitAction(action: string) {
    setError("");
    setNotice("");
    setResult("");
    setLoadingAction(action);
    try {
      const response =
        action === "status"
          ? await getGitStatus()
          : action === "diff"
            ? await getGitDiff()
            : action === "staged"
              ? await getGitStagedDiff()
              : action === "log"
                ? await getGitLog()
                : action === "branch"
                  ? await getGitBranch()
                  : await suggestGitCommitMessage();
      setResult(response.message || "(no output)");
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setLoadingAction("");
    }
  }

  async function handleCommit() {
    const message = commitMessage.trim();
    if (!message) {
      setError("Commit message is required.");
      return;
    }

    setError("");
    setNotice("");
    setResult("");
    setLoadingAction("commit");
    try {
      const response = await createGitCommit({ message });
      setNotice(response.message);
      setCommitMessage("");
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setLoadingAction("");
    }
  }

  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <h1>Git</h1>
          <p>Safe Git helpers for the current project.</p>
        </div>
      </div>

      {error ? <div className="error">{error}</div> : null}
      {notice ? <div className="notice">{notice}</div> : null}

      <section className="gitPanel">
        <div className="buttonRow">
          <button
            type="button"
            disabled={Boolean(loadingAction)}
            onClick={() => void handleGitAction("status")}
          >
            {loadingAction === "status" ? "Loading..." : "Status"}
          </button>
          <button
            type="button"
            disabled={Boolean(loadingAction)}
            onClick={() => void handleGitAction("diff")}
          >
            {loadingAction === "diff" ? "Loading..." : "Diff"}
          </button>
          <button
            type="button"
            disabled={Boolean(loadingAction)}
            onClick={() => void handleGitAction("staged")}
          >
            {loadingAction === "staged" ? "Loading..." : "Staged diff"}
          </button>
          <button
            type="button"
            disabled={Boolean(loadingAction)}
            onClick={() => void handleGitAction("log")}
          >
            {loadingAction === "log" ? "Loading..." : "Log"}
          </button>
          <button
            type="button"
            disabled={Boolean(loadingAction)}
            onClick={() => void handleGitAction("branch")}
          >
            {loadingAction === "branch" ? "Loading..." : "Current branch"}
          </button>
          <button
            type="button"
            disabled={Boolean(loadingAction)}
            onClick={() => void handleGitAction("suggest")}
          >
            {loadingAction === "suggest" ? "Loading..." : "Suggest commit message"}
          </button>
        </div>

        <div className="commitBox">
          <label>
            <span>Commit message</span>
            <input
              value={commitMessage}
              onChange={(event) => setCommitMessage(event.target.value)}
              placeholder="Release hardening"
            />
          </label>
          <button
            type="button"
            disabled={Boolean(loadingAction)}
            onClick={() => void handleCommit()}
          >
            {loadingAction === "commit" ? "Requesting..." : "Commit"}
          </button>
        </div>
        <div className="muted">
          Commit requires approval in the Approvals tab. Git add is not automatic.
        </div>
      </section>

      <pre className="gitOutput">
        <code>{result || "No Git output yet."}</code>
      </pre>
    </section>
  );
}

function ProjectTab() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [currentProject, setCurrentProjectState] = useState<Project | null>(null);
  const [projectCommands, setProjectCommands] = useState<Record<string, string>>({});
  const [projectCommandCwd, setProjectCommandCwd] = useState("");
  const [workspacePreferences, setWorkspacePreferences] = useState<
    Record<string, Record<string, string>>
  >({});
  const [workspacePreferenceForm, setWorkspacePreferenceForm] =
    useState<WorkspacePreferenceForm>(emptyWorkspacePreferenceForm);
  const [editor, setEditor] = useState<ProjectEditorState>(emptyProjectEditorState);
  const [editorDirty, setEditorDirty] = useState(false);
  const [description, setDescription] = useState("");
  const [projectInput, setProjectInput] = useState("Void");
  const [timeoutSeconds, setTimeoutSeconds] = useState(120);
  const [repoOpenMode, setRepoOpenMode] = useState<"visible" | "headless">("visible");
  const [importJson, setImportJson] = useState("");
  const [importResolution, setImportResolution] = useState<"replace" | "rename" | "skip">(
    "skip",
  );
  const [importPreview, setImportPreview] = useState<ProjectImportPreview | null>(null);
  const [importStatus, setImportStatus] = useState<
    "preview" | "pending" | "completed" | "rejected"
  >("preview");
  const [backups, setBackups] = useState<ProjectBackup[]>([]);
  const [selectedBackup, setSelectedBackup] = useState("");
  const [backupPreview, setBackupPreview] = useState<ProjectBackupPreview | null>(null);
  const [backupStatus, setBackupStatus] = useState<
    "preview" | "pending" | "completed" | "rejected"
  >("preview");
  const [exportOutput, setExportOutput] = useState("");
  const [inlineApproval, setInlineApproval] = useState<Approval | null>(null);
  const [inlineClarification, setInlineClarification] =
    useState<ClarificationRequest | null>(null);
  const [clarificationAnswer, setClarificationAnswer] = useState("");
  const [approvalActionId, setApprovalActionId] = useState("");
  const [loading, setLoading] = useState(true);
  const [setting, setSetting] = useState(false);
  const [submittingProjectRegistry, setSubmittingProjectRegistry] = useState(false);
  const [savingWorkspacePreferences, setSavingWorkspacePreferences] = useState(false);
  const [importExportAction, setImportExportAction] = useState("");
  const [runningCommand, setRunningCommand] = useState("");
  const [commandResult, setCommandResult] = useState<StructuredResult | null>(null);
  const [message, setMessage] = useState<StructuredResult | null>(null);
  const [error, setError] = useState("");

  async function loadProjectContext(options?: ProjectEditorRefreshOptions) {
    try {
      setError("");
      setLoading(true);
      const [
        projectsResponse,
        descriptionResponse,
        commandsResponse,
        workspacePreferencesResponse,
        backupsResponse,
      ] = await Promise.all([
        getProjects(),
        describeCurrentProject(),
        getProjectCommands(),
        getWorkspacePreferences(),
        listProjectBackups(),
      ]);
      const clarificationResponse = await getClarification();
      setProjects(projectsResponse.projects);
      setCurrentProjectState(descriptionResponse.project);
      setProjectCommands(commandsResponse.commands);
      setProjectCommandCwd(commandsResponse.cwd);
      setWorkspacePreferences(workspacePreferencesResponse.preferences);
      setWorkspacePreferenceForm(
        workspaceFormFromPreferences(workspacePreferencesResponse.preferences),
      );
      setBackups(backupsResponse.backups);
      setSelectedBackup((current) =>
        current && backupsResponse.backups.some((backup) => backup.filename === current)
          ? current
          : backupsResponse.backups[0]?.filename ?? "",
      );
      setDescription(descriptionResponse.description);
      setEditor((current) =>
        projectEditorForRefresh({
          currentEditor: current,
          editorDirty,
          projects: projectsResponse.projects,
          currentProject: descriptionResponse.project,
          options,
        }),
      );
      setInlineClarification(normalizeClarification(clarificationResponse.pending));
      const pendingApproval = await fetchInlineApproval(
        (approval) =>
          approval.action === "set_current_project" ||
          approval.action === "run_project_command" ||
          approval.action === "run_project_command_visible" ||
          approval.action === "open_project_workspace" ||
          approval.action === "open_project_repo_in_browser" ||
          approval.action === "update_workspace_preferences" ||
          approval.action === "create_project" ||
          approval.action === "update_project" ||
          approval.action === "delete_project" ||
          approval.action === "import_projects" ||
          approval.action === "create_project_backup" ||
          approval.action === "restore_project_backup" ||
          approval.action === "delete_project_backup",
      );
      setInlineApproval(pendingApproval);
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setLoading(false);
    }
  }

  async function handleSetProject() {
    const project = projectInput.trim();
    if (!project) {
      setError("Project id, name, or alias is required.");
      return;
    }

    setError("");
    setMessage(null);
    setInlineApproval(null);
    setSetting(true);
    try {
      const response = await setCurrentProject({ project });
      setMessage(toStructuredResult(response));
      const pendingApproval = await fetchInlineApproval(
        (approval) =>
          approval.id === response.data?.approval_id ||
          approval.action === "set_current_project",
      );
      setInlineApproval(pendingApproval);
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setSetting(false);
    }
  }

  function selectEditorProject(project: Project) {
    setEditor(projectEditorFromProject(project));
    setEditorDirty(false);
    setMessage(null);
    setError("");
  }

  function updateEditor(changes: Partial<ProjectEditorState>) {
    setEditor((current) => ({ ...current, ...changes }));
    setEditorDirty(true);
  }

  function updateEditorWorkspace(field: keyof WorkspacePreferenceForm, value: string) {
    setEditor((current) => ({
      ...current,
      workspace: { ...current.workspace, [field]: value },
    }));
    setEditorDirty(true);
  }

  function validateEditor() {
    const project = projectPayloadFromEditor(editor);
    if (!project.id) return "Project ID is required.";
    if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,63}$/.test(project.id)) {
      return "Project ID must start with a letter or number and contain only letters, numbers, underscores, or hyphens.";
    }
    if (!project.name) return "Project name is required.";
    if (!project.root_path) return "Root path is required.";
    const aliases = project.aliases ?? [];
    if (new Set(aliases.map((alias) => alias.toLowerCase())).size !== aliases.length) {
      return "Duplicate aliases are not allowed.";
    }
    const commandKeys = editor.commands.map((row) => row.key.trim());
    if (commandKeys.some((key) => !key)) return "Command keys must not be empty.";
    if (new Set(commandKeys.map((key) => key.toLowerCase())).size !== commandKeys.length) {
      return "Duplicate command keys are not allowed.";
    }
    return "";
  }

  function handleCreateEditor() {
    setEditor(emptyProjectEditorState());
    setEditorDirty(true);
    setMessage(null);
    setError("");
  }

  async function handleDuplicateEditor(project: Project) {
    const id = project.id;
    if (!id) return;
    setError("");
    setMessage(null);
    try {
      const response = await duplicateProject(id);
      setEditor(projectEditorFromProject(response.project, id));
      setEditorDirty(true);
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    }
  }

  async function handleSaveProjectRegistry() {
    const validationError = validateEditor();
    if (validationError) {
      setError(validationError);
      return;
    }
    const project = projectPayloadFromEditor(editor);
    setError("");
    setMessage(null);
    setCommandResult(null);
    setInlineApproval(null);
    setSubmittingProjectRegistry(true);
    try {
      const response =
        editor.originalId === null
          ? await createProject({
              project,
              duplicate_source_id: editor.duplicateSourceId,
            })
          : await updateProject(editor.originalId, { project });
      setMessage(toStructuredResult(response));
      const pendingApproval = await fetchInlineApproval(
        (approval) =>
          approval.id === response.data?.approval_id ||
          approval.action === "create_project" ||
          approval.action === "update_project",
      );
      setInlineApproval(pendingApproval);
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setSubmittingProjectRegistry(false);
    }
  }

  function handleCancelProjectRegistry() {
    const selected =
      projects.find((project) => project.id === editor.originalId) ??
      currentProject ??
      projects[0];
    setEditor(selected ? projectEditorFromProject(selected) : emptyProjectEditorState());
    setEditorDirty(false);
    setError("");
  }

  async function handleDeleteProjectRegistry(project: Project) {
    const id = project.id;
    if (!id) return;
    const isCurrent = id === currentProject?.id;
    if (
      isCurrent &&
      !window.confirm("Delete the current project and switch to another project?")
    ) {
      return;
    }
    setError("");
    setMessage(null);
    setCommandResult(null);
    setInlineApproval(null);
    setSubmittingProjectRegistry(true);
    try {
      const response = await deleteProject(id, { confirm_current: isCurrent });
      setMessage(toStructuredResult(response));
      const pendingApproval = await fetchInlineApproval(
        (approval) =>
          approval.id === response.data?.approval_id ||
          approval.action === "delete_project",
      );
      setInlineApproval(pendingApproval);
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setSubmittingProjectRegistry(false);
    }
  }

  async function handleSelectCurrentFromRegistry(project: Project) {
    if (!project.id) return;
    setProjectInput(project.id);
    setError("");
    setMessage(null);
    setInlineApproval(null);
    setSetting(true);
    try {
      const response = await setCurrentProject({ project: project.id });
      setMessage(toStructuredResult(response));
      const pendingApproval = await fetchInlineApproval(
        (approval) =>
          approval.id === response.data?.approval_id ||
          approval.action === "set_current_project",
      );
      setInlineApproval(pendingApproval);
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setSetting(false);
    }
  }

  async function handleExportProject(scope: "current" | "selected" | "all") {
    const selectedId = editor.originalId || editor.id || currentProject?.id || "";
    if (scope === "selected" && !selectedId) {
      setError("Select a project to export.");
      return;
    }

    setError("");
    setMessage(null);
    setImportExportAction(`export:${scope}`);
    try {
      const response =
        scope === "current"
          ? await exportCurrentProject()
          : scope === "all"
            ? await exportAllProjects()
            : await exportProject(selectedId);
      setExportOutput(formatProjectExport(response.export));
      setMessage({
        message: `Exported ${response.export.projects.length} project(s).`,
      });
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setImportExportAction("");
    }
  }

  function parsedImportSource() {
    return parseProjectImportJson(importJson);
  }

  async function handleValidateImport() {
    setError("");
    setMessage(null);
    setImportPreview(null);
    setImportStatus("preview");
    setImportExportAction("validate-import");
    try {
      const response = await validateProjectImport({
        source: parsedImportSource(),
        resolution: importResolution,
      });
      setImportPreview(response.preview);
      setMessage({ message: response.preview.summary || "Project import preview." });
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setImportExportAction("");
    }
  }

  async function handleImportProjects() {
    setError("");
    setMessage(null);
    setInlineApproval(null);
    setImportStatus("preview");
    setImportExportAction("import-projects");
    try {
      const source = parsedImportSource();
      const previewResponse = await validateProjectImport({
        source,
        resolution: importResolution,
      });
      setImportPreview(previewResponse.preview);
      if (previewResponse.preview.errors.length > 0) {
        setMessage({ message: previewResponse.preview.summary || "Validation failed." });
        return;
      }
      const response = await importProjects({ source, resolution: importResolution });
      setMessage(toStructuredResult(response));
      const pendingApproval = await fetchInlineApproval(
        (approval) =>
          approval.id === response.data?.approval_id ||
          approval.action === "import_projects",
      );
      setInlineApproval(pendingApproval);
      setImportStatus("pending");
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setImportExportAction("");
    }
  }

  function handleCancelImport() {
    setImportJson("");
    setImportPreview(null);
    setImportStatus("preview");
    setError("");
  }

  async function handleRefreshBackups() {
    setError("");
    setImportExportAction("refresh-backups");
    try {
      const response = await listProjectBackups();
      setBackups(response.backups);
      setSelectedBackup((current) =>
        current && response.backups.some((backup) => backup.filename === current)
          ? current
          : response.backups[0]?.filename ?? "",
      );
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setImportExportAction("");
    }
  }

  async function handleCreateBackup() {
    setError("");
    setMessage(null);
    setInlineApproval(null);
    setBackupStatus("preview");
    setImportExportAction("create-backup");
    try {
      const response = await createProjectBackup();
      setMessage(toStructuredResult(response));
      const pendingApproval = await fetchInlineApproval(
        (approval) =>
          approval.id === response.data?.approval_id ||
          approval.action === "create_project_backup",
      );
      setInlineApproval(pendingApproval);
      setBackupStatus("pending");
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setImportExportAction("");
    }
  }

  async function handleValidateBackup(filename = selectedBackup) {
    if (!filename) {
      setError("Select a backup.");
      return;
    }
    setError("");
    setMessage(null);
    setBackupPreview(null);
    setBackupStatus("preview");
    setImportExportAction("validate-backup");
    try {
      const response = await validateProjectBackup({ filename });
      setSelectedBackup(filename);
      setBackupPreview(response.preview);
      setMessage({ message: response.preview.summary || "Project backup preview." });
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setImportExportAction("");
    }
  }

  async function handleRestoreBackup(filename = selectedBackup) {
    if (!filename) {
      setError("Select a backup.");
      return;
    }
    setError("");
    setMessage(null);
    setInlineApproval(null);
    setBackupStatus("preview");
    setImportExportAction("restore-backup");
    try {
      const previewResponse = await validateProjectBackup({ filename });
      setSelectedBackup(filename);
      setBackupPreview(previewResponse.preview);
      if (previewResponse.preview.errors.length > 0) {
        setMessage({ message: previewResponse.preview.summary || "Validation failed." });
        return;
      }
      const response = await restoreProjectBackup({ filename });
      setMessage(toStructuredResult(response));
      const pendingApproval = await fetchInlineApproval(
        (approval) =>
          approval.id === response.data?.approval_id ||
          approval.action === "restore_project_backup",
      );
      setInlineApproval(pendingApproval);
      setBackupStatus("pending");
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setImportExportAction("");
    }
  }

  async function handleDeleteBackup(filename = selectedBackup) {
    if (!filename) {
      setError("Select a backup.");
      return;
    }
    if (!window.confirm(`Delete backup ${filename}?`)) {
      return;
    }
    setError("");
    setMessage(null);
    setInlineApproval(null);
    setImportExportAction("delete-backup");
    try {
      const response = await deleteProjectBackup({ filename });
      setMessage(toStructuredResult(response));
      const pendingApproval = await fetchInlineApproval(
        (approval) =>
          approval.id === response.data?.approval_id ||
          approval.action === "delete_project_backup",
      );
      setInlineApproval(pendingApproval);
      setBackupStatus("pending");
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setImportExportAction("");
    }
  }

  async function handleRunCommand(commandKey: string) {
    setError("");
    setMessage(null);
    setCommandResult(null);
    setInlineApproval(null);
    setRunningCommand(commandKey);
    try {
      const response = await runProjectCommand(commandKey, {
        timeout_seconds: timeoutSeconds,
      });
      setMessage(toStructuredResult(response));
      const pendingApproval = await fetchInlineApproval(
        (approval) =>
          approval.id === response.data?.approval_id ||
          approval.action === "run_project_command",
      );
      setInlineApproval(pendingApproval);
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setRunningCommand("");
    }
  }

  async function handleRunCommandVisible(commandKey: string) {
    setError("");
    setMessage(null);
    setCommandResult(null);
    setInlineApproval(null);
    setRunningCommand(`${commandKey}:terminal`);
    try {
      const response = await runProjectCommandVisible(commandKey);
      setMessage(toStructuredResult(response));
      const pendingApproval = await fetchInlineApproval(
        (approval) =>
          approval.id === response.data?.approval_id ||
          approval.action === "run_project_command_visible",
      );
      setInlineApproval(pendingApproval);
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setRunningCommand("");
    }
  }

  async function handleOpenRepo() {
    const project = currentProject?.id ?? currentProject?.name ?? "";
    if (!project) {
      setError("Current project is required.");
      return;
    }

    setError("");
    setMessage(null);
    setCommandResult(null);
    setInlineApproval(null);
    setRunningCommand("open-repo");
    try {
      const response = await openProjectRepo({ project, mode: repoOpenMode });
      setMessage(toStructuredResult(response));
      const pendingApproval = await fetchInlineApproval(
        (approval) =>
          approval.id === response.data?.approval_id ||
          approval.action === "open_project_repo_in_browser",
      );
      setInlineApproval(pendingApproval);
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setRunningCommand("");
    }
  }

  async function handleOpenWorkspace(target: "terminal" | "finder" | "github" | "browser") {
    setError("");
    setMessage(null);
    setCommandResult(null);
    setInlineApproval(null);
    setRunningCommand(`workspace:${target}`);
    try {
      const response = await openProjectWorkspace({ target });
      setMessage(toStructuredResult(response));
      const pendingApproval = await fetchInlineApproval(
        (approval) =>
          approval.id === response.data?.approval_id ||
          approval.action === "open_project_workspace",
      );
      setInlineApproval(pendingApproval);
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setRunningCommand("");
    }
  }

  function updateWorkspacePreferenceForm(
    field: keyof WorkspacePreferenceForm,
    value: string,
  ) {
    setWorkspacePreferenceForm((current) => ({ ...current, [field]: value }));
  }

  async function handleSaveWorkspacePreferences() {
    const original = workspaceFormFromPreferences(workspacePreferences);
    const changes: Array<{ section: string; field: string; value: string }> = [
      {
        section: "terminal",
        field: "app",
        value: workspacePreferenceForm.terminalApp,
      },
      {
        section: "terminal",
        field: "command",
        value: workspacePreferenceForm.terminalCommand,
      },
      {
        section: "terminal",
        field: "reuse_existing",
        value: workspacePreferenceForm.terminalReuseExisting,
      },
      {
        section: "terminal",
        field: "open_mode",
        value: workspacePreferenceForm.terminalOpenMode,
      },
      {
        section: "terminal",
        field: "profile",
        value: workspacePreferenceForm.terminalProfile,
      },
      {
        section: "terminal",
        field: "window_bounds",
        value: workspacePreferenceForm.terminalWindowBounds,
      },
      {
        section: "browser",
        field: "app",
        value: workspacePreferenceForm.browserApp,
      },
      {
        section: "file_manager",
        field: "app",
        value: workspacePreferenceForm.fileManagerApp,
      },
    ].filter((change) => {
      const key =
        change.section === "terminal" && change.field === "app"
          ? "terminalApp"
          : change.section === "terminal" && change.field === "command"
            ? "terminalCommand"
            : change.section === "terminal" && change.field === "reuse_existing"
              ? "terminalReuseExisting"
              : change.section === "terminal" && change.field === "open_mode"
                ? "terminalOpenMode"
                : change.section === "terminal" && change.field === "profile"
                  ? "terminalProfile"
                  : change.section === "terminal" && change.field === "window_bounds"
                    ? "terminalWindowBounds"
                    : change.section === "browser"
                      ? "browserApp"
                      : "fileManagerApp";
      return change.value !== original[key as keyof WorkspacePreferenceForm];
    });

    if (changes.length === 0) {
      setMessage({ message: "No workspace preference changes to save." });
      return;
    }

    setError("");
    setMessage(null);
    setCommandResult(null);
    setInlineApproval(null);
    setSavingWorkspacePreferences(true);
    try {
      const response = await updateWorkspacePreferences({ changes });
      setMessage(toStructuredResult(response));
      const pendingApproval = await fetchInlineApproval(
        (approval) =>
          approval.id === response.data?.approval_id ||
          approval.action === "update_workspace_preferences",
      );
      setInlineApproval(pendingApproval);
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setSavingWorkspacePreferences(false);
    }
  }

  async function handleApprovalAction(id: string, action: ApprovalAction) {
    setApprovalActionId(id);
    setError("");
    setMessage(null);
    const approvedAction = inlineApproval?.action;
    const isProjectRegistryApproval =
      approvedAction === "create_project" ||
      approvedAction === "update_project" ||
      approvedAction === "delete_project" ||
      approvedAction === "import_projects" ||
      approvedAction === "create_project_backup" ||
      approvedAction === "restore_project_backup" ||
      approvedAction === "delete_project_backup";
    try {
      const response = await resolveInlineApproval(id, action);
      if (
        action === "approve" &&
        (approvedAction === "run_project_command" ||
          approvedAction === "run_project_command_visible" ||
          approvedAction === "open_project_repo_in_browser" ||
          approvedAction === "open_project_workspace")
      ) {
        setCommandResult(toStructuredResult(response));
      } else {
        setMessage(toStructuredResult(response));
      }
      if (approvedAction === "import_projects" && action === "reject") {
        setImportStatus("rejected");
      }
      if (
        (approvedAction === "create_project_backup" ||
          approvedAction === "restore_project_backup" ||
          approvedAction === "delete_project_backup") &&
        action === "reject"
      ) {
        setBackupStatus("rejected");
      }
      setInlineApproval(null);
      if (action === "approve" && isProjectRegistryApproval) {
        setEditorDirty(false);
        const resultProject = asRecord(response.data?.project);
        const preferredProjectId =
          approvedAction === "delete_project" ||
          approvedAction === "import_projects" ||
          approvedAction === "restore_project_backup" ||
          approvedAction === "delete_project_backup" ||
          approvedAction === "create_project_backup"
            ? null
            : asText(resultProject?.id, "");
        await loadProjectContext({
          forceEditorRefresh: true,
          preferredProjectId: preferredProjectId || null,
        });
        if (approvedAction === "import_projects") {
          setImportStatus(action === "approve" ? "completed" : "rejected");
        }
        if (
          approvedAction === "create_project_backup" ||
          approvedAction === "restore_project_backup" ||
          approvedAction === "delete_project_backup"
        ) {
          setBackupStatus("completed");
        }
        return;
      }
      if (
        (action === "approve" || approvedAction !== "update_workspace_preferences") &&
        !isProjectRegistryApproval
      ) {
        await loadProjectContext();
      }
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setApprovalActionId("");
    }
  }

  async function handleClarificationSubmit() {
    const answer = clarificationAnswer.trim();
    if (!answer) {
      return;
    }

    setError("");
    setMessage(null);
    setCommandResult(null);
    setRunningCommand("clarification");
    try {
      const response = await respondToClarification({ answer });
      if (response.result_type === "clarification_request" && response.clarification) {
        setInlineClarification(response.clarification);
      } else {
        setInlineClarification(null);
      }
      setClarificationAnswer("");
      if (mentionsApproval(response.response)) {
        setMessage(toStructuredResult(response));
        const pendingApproval = await fetchInlineApproval(
          (approval) =>
            approval.id === response.data?.approval_id ||
            approval.action === "set_current_project" ||
            approval.action === "run_project_command" ||
            approval.action === "run_project_command_visible" ||
            approval.action === "open_project_workspace" ||
            approval.action === "open_project_repo_in_browser" ||
            approval.action === "update_workspace_preferences" ||
            approval.action === "create_project" ||
            approval.action === "update_project" ||
            approval.action === "delete_project" ||
            approval.action === "import_projects" ||
            approval.action === "create_project_backup" ||
            approval.action === "restore_project_backup" ||
            approval.action === "delete_project_backup",
        );
        setInlineApproval(pendingApproval);
      } else {
        setCommandResult(toStructuredResult(response));
      }
      await loadProjectContext();
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setRunningCommand("");
    }
  }

  useEffect(() => {
    void loadProjectContext();
  }, []);

  const commandKeys = Object.keys(projectCommands).sort();

  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <h1>Projects</h1>
          <p>Project context stored in local JSON memory.</p>
        </div>
        <button
          className="secondaryButton"
          type="button"
          onClick={() => void loadProjectContext()}
        >
          Refresh
        </button>
      </div>

      {error ? <div className="error">{error}</div> : null}
      {message ? <ResultBlock result={message} /> : null}
      {inlineApproval ? (
        <InlineApprovalCard
          approval={inlineApproval}
          resolving={approvalActionId === inlineApproval.id}
          onResolve={handleApprovalAction}
        />
      ) : null}
      {inlineClarification ? (
        <InlineClarificationCard
          clarification={inlineClarification}
          answer={clarificationAnswer}
          submitting={runningCommand === "clarification"}
          onAnswerChange={setClarificationAnswer}
          onSubmit={() => void handleClarificationSubmit()}
        />
      ) : null}

      <section className="projectPanel">
        <div className="projectSummary">
          <div className="sectionLabel">Current project</div>
          <h2>{currentProject?.name ?? (loading ? "Loading..." : "Unknown")}</h2>
          <div className="field">
            <span>ID</span>
            <p>{currentProject?.id ?? "unknown"}</p>
          </div>
          <div className="field">
            <span>Repo URL</span>
            <p>{currentProject?.repo_url || "none"}</p>
          </div>
          <div className="field">
            <span>Root path</span>
            <p>{currentProject?.root_path || "."}</p>
          </div>
          <div className="field">
            <span>Aliases</span>
            <p>{currentProject?.aliases?.join(", ") || "none"}</p>
          </div>
          <div className="field">
            <span>Command keys</span>
            <p>{commandKeys.join(", ") || "none"}</p>
          </div>
          <div className="field">
            <span>Workspace targets</span>
            <p>
              {currentProject?.workspace
                ? Object.keys(currentProject.workspace).sort().join(", ") || "none"
                : "none"}
            </p>
          </div>
          <div className="buttonRow">
            <label className="timeoutControl">
              <span>Mode</span>
              <select
                value={repoOpenMode}
                onChange={(event) =>
                  setRepoOpenMode(event.target.value as "visible" | "headless")
                }
              >
                <option value="visible">visible</option>
                <option value="headless">headless</option>
              </select>
            </label>
            <button
              type="button"
              disabled={Boolean(runningCommand) || !currentProject?.repo_url}
              onClick={() => void handleOpenRepo()}
            >
              {runningCommand === "open-repo"
                ? "Requesting..."
                : "Open repo in browser"}
            </button>
          </div>
        </div>

        <div className="projectSwitcher">
          <label>
            <span>Set current project</span>
            <input
              value={projectInput}
              onChange={(event) => setProjectInput(event.target.value)}
              placeholder="Void"
            />
          </label>
          <button
            type="button"
            disabled={setting}
            onClick={() => void handleSetProject()}
          >
            {setting ? "Requesting..." : "Set project"}
          </button>
        </div>

        <pre className="gitOutput">
          <code>{description || "No project description loaded."}</code>
        </pre>
      </section>

      <section className="contentSection">
        <div className="sectionHeader">
          <div>
            <h2>Workspace</h2>
            <p>{currentProject?.root_path || "."}</p>
          </div>
        </div>
        <div className="buttonRow">
          <button
            type="button"
            disabled={Boolean(runningCommand)}
            onClick={() => void handleOpenWorkspace("terminal")}
          >
            {runningCommand === "workspace:terminal" ? "Requesting..." : "Open Workspace"}
          </button>
          <button
            className="secondaryButton"
            type="button"
            disabled={Boolean(runningCommand)}
            onClick={() => void handleOpenWorkspace("finder")}
          >
            {runningCommand === "workspace:finder" ? "Requesting..." : "Open Finder"}
          </button>
          <button
            className="secondaryButton"
            type="button"
            disabled={Boolean(runningCommand) || !currentProject?.repo_url}
            onClick={() => void handleOpenWorkspace("github")}
          >
            {runningCommand === "workspace:github" ? "Requesting..." : "Open GitHub"}
          </button>
          <button
            className="secondaryButton"
            type="button"
            disabled={Boolean(runningCommand) || !currentProject?.repo_url}
            onClick={() => void handleOpenWorkspace("browser")}
          >
            {runningCommand === "workspace:browser" ? "Requesting..." : "Open Browser"}
          </button>
        </div>
      </section>

      <section className="contentSection">
        <div className="sectionHeader">
          <div>
            <h2>Workspace Preferences</h2>
            <p>Editable project workspace configuration.</p>
          </div>
          <button
            type="button"
            disabled={
              savingWorkspacePreferences ||
              inlineApproval?.action === "update_workspace_preferences"
            }
            onClick={() => void handleSaveWorkspacePreferences()}
          >
            {savingWorkspacePreferences
              ? "Requesting..."
              : inlineApproval?.action === "update_workspace_preferences"
                ? "Pending approval"
                : "Save"}
          </button>
        </div>
        <div className="formGrid">
          <label>
            <span>Terminal app</span>
            <select
              value={workspacePreferenceForm.terminalApp}
              onChange={(event) =>
                updateWorkspacePreferenceForm("terminalApp", event.target.value)
              }
            >
              <option value="">unset</option>
              <option value="terminal">terminal</option>
              <option value="iterm">iterm</option>
              <option value="iterm2">iterm2</option>
            </select>
          </label>
          <label>
            <span>Command</span>
            <input
              value={workspacePreferenceForm.terminalCommand}
              onChange={(event) =>
                updateWorkspacePreferenceForm("terminalCommand", event.target.value)
              }
              placeholder="cd {root} && nvim ."
            />
          </label>
          <label>
            <span>Reuse existing</span>
            <select
              value={workspacePreferenceForm.terminalReuseExisting}
              onChange={(event) =>
                updateWorkspacePreferenceForm("terminalReuseExisting", event.target.value)
              }
            >
              <option value="">unset</option>
              <option value="true">true</option>
              <option value="false">false</option>
            </select>
          </label>
          <label>
            <span>Open mode</span>
            <select
              value={workspacePreferenceForm.terminalOpenMode}
              onChange={(event) =>
                updateWorkspacePreferenceForm("terminalOpenMode", event.target.value)
              }
            >
              <option value="">unset</option>
              <option value="tab">tab</option>
              <option value="window">window</option>
            </select>
          </label>
          <label>
            <span>Profile</span>
            <input
              value={workspacePreferenceForm.terminalProfile}
              onChange={(event) =>
                updateWorkspacePreferenceForm("terminalProfile", event.target.value)
              }
              placeholder="Development"
            />
          </label>
          <label>
            <span>Window bounds</span>
            <input
              value={workspacePreferenceForm.terminalWindowBounds}
              onChange={(event) =>
                updateWorkspacePreferenceForm("terminalWindowBounds", event.target.value)
              }
              placeholder="100,80,1500,950"
            />
          </label>
          <label>
            <span>Browser</span>
            <input
              value={workspacePreferenceForm.browserApp}
              onChange={(event) =>
                updateWorkspacePreferenceForm("browserApp", event.target.value)
              }
              placeholder="Safari"
            />
          </label>
          <label>
            <span>File manager</span>
            <input
              value={workspacePreferenceForm.fileManagerApp}
              onChange={(event) =>
                updateWorkspacePreferenceForm("fileManagerApp", event.target.value)
              }
              placeholder="Finder"
            />
          </label>
        </div>
      </section>

      <section className="contentSection">
        <div className="sectionHeader">
          <div>
            <h2>Project Commands</h2>
            <p>{projectCommandCwd || "No command cwd loaded."}</p>
          </div>
          <label className="timeoutControl">
            <span>Timeout</span>
            <input
              type="number"
              min="1"
              max="3600"
              value={timeoutSeconds}
              onChange={(event) =>
                setTimeoutSeconds(Number.parseInt(event.target.value, 10) || 120)
              }
            />
          </label>
        </div>
        <div className="commandList">
          {commandKeys.length === 0 ? (
            <EmptyState>No project commands configured.</EmptyState>
          ) : (
            commandKeys.map((key) => (
              <article className="commandItem" key={key}>
                <div>
                  <h3>{key}</h3>
                  <code>{projectCommands[key]}</code>
                </div>
                <div className="buttonRow">
                  <button
                    type="button"
                    disabled={Boolean(runningCommand)}
                    onClick={() => void handleRunCommand(key)}
                  >
                    {runningCommand === key ? "Requesting..." : "Run"}
                  </button>
                  <button
                    className="secondaryButton"
                    type="button"
                    disabled={Boolean(runningCommand)}
                    onClick={() => void handleRunCommandVisible(key)}
                  >
                    {runningCommand === `${key}:terminal`
                      ? "Requesting..."
                      : "Run in Terminal"}
                  </button>
                </div>
              </article>
            ))
          )}
        </div>
        {commandResult ? (
          <ResultBlock result={commandResult} />
        ) : (
          <pre className="gitOutput">
            <code>No command result yet.</code>
          </pre>
        )}
      </section>

      <section className="contentSection">
        <div className="sectionHeader">
          <div>
            <h2>Project Registry</h2>
            <p>{editorDirty ? "Unsaved changes" : "No unsaved changes"}</p>
          </div>
          <button type="button" onClick={handleCreateEditor}>
            Create
          </button>
        </div>
        <div className="importExportPanel">
          <section>
            <div className="sectionHeader compact">
              <h3>Export</h3>
            </div>
            <div className="buttonRow">
              <button
                className="secondaryButton"
                type="button"
                disabled={Boolean(importExportAction)}
                onClick={() => void handleExportProject("current")}
              >
                {importExportAction === "export:current" ? "Exporting..." : "Export current"}
              </button>
              <button
                className="secondaryButton"
                type="button"
                disabled={Boolean(importExportAction)}
                onClick={() => void handleExportProject("selected")}
              >
                {importExportAction === "export:selected"
                  ? "Exporting..."
                  : "Export selected"}
              </button>
              <button
                className="secondaryButton"
                type="button"
                disabled={Boolean(importExportAction)}
                onClick={() => void handleExportProject("all")}
              >
                {importExportAction === "export:all" ? "Exporting..." : "Export all"}
              </button>
            </div>
            {exportOutput ? (
              <pre className="gitOutput">
                <code>{exportOutput}</code>
              </pre>
            ) : null}
          </section>

          <section>
            <div className="sectionHeader compact">
              <div>
                <h3>Import</h3>
                <p>{importPreviewStatus(importPreview)}</p>
              </div>
              <span className={`importStatus ${importStatus}`}>{importStatus}</span>
            </div>
            <div className="formGrid">
              <label>
                <span>Conflict resolution</span>
                <select
                  value={importResolution}
                  onChange={(event) =>
                    setImportResolution(
                      event.target.value === "replace"
                        ? "replace"
                        : event.target.value === "rename"
                          ? "rename"
                          : "skip",
                    )
                  }
                >
                  <option value="skip">skip imported conflicts</option>
                  <option value="replace">replace existing projects</option>
                  <option value="rename">rename imported projects</option>
                </select>
              </label>
            </div>
            <label className="importJsonField">
              <span>Project import JSON</span>
              <textarea
                value={importJson}
                onChange={(event) => setImportJson(event.target.value)}
                rows={8}
                placeholder={'{"version":1,"projects":[{"id":"demo","name":"Demo","root_path":"."}]}'}
              />
            </label>
            <div className="buttonRow">
              <button
                className="secondaryButton"
                type="button"
                disabled={Boolean(importExportAction)}
                onClick={() => void handleValidateImport()}
              >
                {importExportAction === "validate-import" ? "Validating..." : "Validate"}
              </button>
              <button
                type="button"
                disabled={
                  Boolean(importExportAction) ||
                  inlineApproval?.action === "import_projects"
                }
                onClick={() => void handleImportProjects()}
              >
                {inlineApproval?.action === "import_projects"
                  ? "Pending approval"
                  : importExportAction === "import-projects"
                    ? "Requesting..."
                    : "Approve import"}
              </button>
              <button
                className="secondaryButton"
                type="button"
                disabled={Boolean(importExportAction)}
                onClick={handleCancelImport}
              >
                Cancel
              </button>
            </div>
            {importPreview ? (
              <div className="importPreviewGrid">
                <article className="importPreviewBlock">
                  <div className="sectionLabel">Projects to create</div>
                  {importPreview.creates.length === 0 ? (
                    <p>none</p>
                  ) : (
                    <ul>
                      {importPreview.creates.map((project) => (
                        <li key={project.id}>{project.name ?? project.id}</li>
                      ))}
                    </ul>
                  )}
                </article>
                <article className="importPreviewBlock">
                  <div className="sectionLabel">Projects to replace</div>
                  {importPreview.replaces.length === 0 ? (
                    <p>none</p>
                  ) : (
                    <ul>
                      {importPreview.replaces.map((project) => (
                        <li key={project.id}>{project.name ?? project.id}</li>
                      ))}
                    </ul>
                  )}
                </article>
                <article className="importPreviewBlock">
                  <div className="sectionLabel">Projects to skip</div>
                  {importPreview.skips.length === 0 ? (
                    <p>none</p>
                  ) : (
                    <ul>
                      {importPreview.skips.map((project) => (
                        <li key={project.id}>{project.name ?? project.id}</li>
                      ))}
                    </ul>
                  )}
                </article>
                <article className="importPreviewBlock importPreviewWide">
                  <div className="sectionLabel">Alias ownership changes</div>
                  {importPreviewAliasOwnershipChanges(importPreview).length === 0 ? (
                    <p>none</p>
                  ) : (
                    <ul>
                      {importPreviewAliasOwnershipChanges(importPreview).map((change) => (
                        <li key={change.key}>{change.text}</li>
                      ))}
                    </ul>
                  )}
                </article>
                <article className="importPreviewBlock importPreviewWide">
                  <div className="sectionLabel">Alias renames</div>
                  {importPreviewAliasRenames(importPreview).length === 0 ? (
                    <p>none</p>
                  ) : (
                    <ul>
                      {importPreviewAliasRenames(importPreview).map((change) => (
                        <li key={change.key}>{change.text}</li>
                      ))}
                    </ul>
                  )}
                </article>
                <article className="importPreviewBlock">
                  <div className="sectionLabel">Warnings</div>
                  {importPreview.warnings.length === 0 ? (
                    <p>none</p>
                  ) : (
                    <ul>
                      {importPreview.warnings.map((warning) => (
                        <li key={warning}>{warning}</li>
                      ))}
                    </ul>
                  )}
                </article>
                <article className="importPreviewBlock importPreviewWide">
                  <div className="sectionLabel">Validation errors</div>
                  {importPreview.errors.length === 0 ? (
                    <p>none</p>
                  ) : (
                    <ul>
                      {importPreview.errors.map((validationError) => (
                        <li key={validationError}>{validationError}</li>
                      ))}
                    </ul>
                  )}
                </article>
              </div>
            ) : null}
          </section>

          <section>
            <div className="sectionHeader compact">
              <div>
                <h3>Backup</h3>
                <p>{backupPreviewStatus(backupPreview)}</p>
              </div>
              <span className={`importStatus ${backupStatus}`}>{backupStatus}</span>
            </div>
            <div className="buttonRow">
              <button
                type="button"
                disabled={Boolean(importExportAction)}
                onClick={() => void handleCreateBackup()}
              >
                {importExportAction === "create-backup" ? "Requesting..." : "Create Backup"}
              </button>
              <button
                className="secondaryButton"
                type="button"
                disabled={Boolean(importExportAction)}
                onClick={() => void handleRefreshBackups()}
              >
                {importExportAction === "refresh-backups" ? "Refreshing..." : "Refresh List"}
              </button>
            </div>
            <div className="backupList">
              {backups.length === 0 ? (
                <EmptyState>No backups found.</EmptyState>
              ) : (
                backups.map((backup) => {
                  const isSelected = backup.filename === selectedBackup;
                  return (
                    <article
                      className={`backupItem${isSelected ? " selected" : ""}`}
                      key={backup.filename}
                    >
                      <button
                        type="button"
                        onClick={() => {
                          setSelectedBackup(backup.filename);
                          setBackupPreview(null);
                          setBackupStatus("preview");
                        }}
                      >
                        <span>{backup.filename}</span>
                        <small>
                          {backup.created_at || "unknown"} ·{" "}
                          {backup.project_count ?? "unknown"} project(s) ·{" "}
                          {formatBackupSize(backup.size)}
                        </small>
                      </button>
                      <div className="registryActions">
                        <button
                          className="secondaryButton"
                          type="button"
                          disabled={Boolean(importExportAction)}
                          onClick={() => void handleValidateBackup(backup.filename)}
                        >
                          Validate
                        </button>
                        <button
                          type="button"
                          disabled={
                            Boolean(importExportAction) ||
                            inlineApproval?.action === "restore_project_backup"
                          }
                          onClick={() => void handleRestoreBackup(backup.filename)}
                        >
                          {inlineApproval?.action === "restore_project_backup"
                            ? "Pending approval"
                            : "Restore"}
                        </button>
                        <button
                          className="dangerButton"
                          type="button"
                          disabled={
                            Boolean(importExportAction) ||
                            inlineApproval?.action === "delete_project_backup"
                          }
                          onClick={() => void handleDeleteBackup(backup.filename)}
                        >
                          Delete
                        </button>
                      </div>
                    </article>
                  );
                })
              )}
            </div>
            {backupPreview ? (
              <div className="importPreviewGrid">
                <article className="importPreviewBlock">
                  <div className="sectionLabel">Backup</div>
                  <p>{backupPreview.filename || selectedBackup || "unknown"}</p>
                </article>
                <article className="importPreviewBlock">
                  <div className="sectionLabel">Created</div>
                  <p>{backupPreview.created_at || "unknown"}</p>
                </article>
                <article className="importPreviewBlock">
                  <div className="sectionLabel">Current project</div>
                  <p>{backupPreview.current_project || "unknown"}</p>
                </article>
                <article className="importPreviewBlock importPreviewWide">
                  <div className="sectionLabel">Projects that will exist</div>
                  {backupPreview.projects.length === 0 ? (
                    <p>none</p>
                  ) : (
                    <ul>
                      {backupPreview.projects.map((project) => (
                        <li key={project.id ?? project.name}>
                          {project.name ?? project.id} ({project.id ?? "unknown"})
                        </li>
                      ))}
                    </ul>
                  )}
                </article>
                <article className="importPreviewBlock">
                  <div className="sectionLabel">Warnings</div>
                  {backupPreview.warnings.length === 0 ? (
                    <p>none</p>
                  ) : (
                    <ul>
                      {backupPreview.warnings.map((warning) => (
                        <li key={warning}>{warning}</li>
                      ))}
                    </ul>
                  )}
                </article>
                <article className="importPreviewBlock importPreviewWide">
                  <div className="sectionLabel">Validation errors</div>
                  {backupPreview.errors.length === 0 ? (
                    <p>none</p>
                  ) : (
                    <ul>
                      {backupPreview.errors.map((validationError) => (
                        <li key={validationError}>{validationError}</li>
                      ))}
                    </ul>
                  )}
                </article>
              </div>
            ) : null}
          </section>
        </div>
        <div className="registryLayout">
          <div className="registryList">
            {projects.length === 0 ? (
              <EmptyState>No projects configured.</EmptyState>
            ) : (
              projects.map((project) => {
                const isCurrent = project.id === currentProject?.id;
                const isSelected = project.id === editor.originalId;
                return (
                  <article
                    className={`registryItem${isSelected ? " selected" : ""}`}
                    key={project.id ?? project.name}
                  >
                    <button type="button" onClick={() => selectEditorProject(project)}>
                      <span>{project.name}</span>
                      <small>{project.id}</small>
                    </button>
                    {isCurrent ? <strong>Current</strong> : null}
                    <div className="registryActions">
                      <button
                        className="secondaryButton"
                        type="button"
                        disabled={setting}
                        onClick={() => void handleSelectCurrentFromRegistry(project)}
                      >
                        Select
                      </button>
                      <button
                        className="secondaryButton"
                        type="button"
                        onClick={() => void handleDuplicateEditor(project)}
                      >
                        Duplicate
                      </button>
                      <button
                        className="dangerButton"
                        type="button"
                        disabled={projects.length <= 1 || submittingProjectRegistry}
                        onClick={() => void handleDeleteProjectRegistry(project)}
                      >
                        Delete
                      </button>
                    </div>
                  </article>
                );
              })
            )}
          </div>
          <div className="registryEditor">
            <div className="formGrid">
              <label>
                <span>ID</span>
                <input
                  value={editor.id}
                  onChange={(event) => updateEditor({ id: event.target.value })}
                />
              </label>
              <label>
                <span>Name</span>
                <input
                  value={editor.name}
                  onChange={(event) => updateEditor({ name: event.target.value })}
                />
              </label>
              <label>
                <span>Root path</span>
                <input
                  value={editor.rootPath}
                  onChange={(event) => updateEditor({ rootPath: event.target.value })}
                />
              </label>
              <label>
                <span>Repository URL</span>
                <input
                  value={editor.repoUrl}
                  onChange={(event) => updateEditor({ repoUrl: event.target.value })}
                />
              </label>
            </div>

            <div className="editorSubsection">
              <div className="sectionHeader compact">
                <h3>Aliases</h3>
                <button
                  className="secondaryButton"
                  type="button"
                  onClick={() => updateEditor({ aliases: [...editor.aliases, ""] })}
                >
                  Add
                </button>
              </div>
              {editor.aliases.length === 0 ? <EmptyState>No aliases.</EmptyState> : null}
              {editor.aliases.map((alias, index) => (
                <div className="editableRow" key={`alias-${index}`}>
                  <input
                    value={alias}
                    onChange={(event) => {
                      const aliases = [...editor.aliases];
                      aliases[index] = event.target.value;
                      updateEditor({ aliases });
                    }}
                  />
                  <button
                    className="secondaryButton"
                    type="button"
                    disabled={index === 0}
                    onClick={() => {
                      const aliases = [...editor.aliases];
                      [aliases[index - 1], aliases[index]] = [aliases[index], aliases[index - 1]];
                      updateEditor({ aliases });
                    }}
                  >
                    Up
                  </button>
                  <button
                    className="secondaryButton"
                    type="button"
                    disabled={index === editor.aliases.length - 1}
                    onClick={() => {
                      const aliases = [...editor.aliases];
                      [aliases[index], aliases[index + 1]] = [aliases[index + 1], aliases[index]];
                      updateEditor({ aliases });
                    }}
                  >
                    Down
                  </button>
                  <button
                    className="dangerButton"
                    type="button"
                    onClick={() =>
                      updateEditor({
                        aliases: editor.aliases.filter((_, aliasIndex) => aliasIndex !== index),
                      })
                    }
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>

            <div className="editorSubsection">
              <div className="sectionHeader compact">
                <h3>Commands</h3>
                <button
                  className="secondaryButton"
                  type="button"
                  onClick={() =>
                    updateEditor({
                      commands: [
                        ...editor.commands,
                        { id: `new-${Date.now()}`, key: "", command: "" },
                      ],
                    })
                  }
                >
                  Add
                </button>
              </div>
              {editor.commands.length === 0 ? <EmptyState>No commands.</EmptyState> : null}
              {editor.commands.map((row, index) => (
                <div className="editableRow commandEditorRow" key={row.id}>
                  <input
                    value={row.key}
                    placeholder="key"
                    onChange={(event) => {
                      const commands = [...editor.commands];
                      commands[index] = { ...row, key: event.target.value };
                      updateEditor({ commands });
                    }}
                  />
                  <input
                    value={row.command}
                    placeholder="command"
                    onChange={(event) => {
                      const commands = [...editor.commands];
                      commands[index] = { ...row, command: event.target.value };
                      updateEditor({ commands });
                    }}
                  />
                  <button
                    className="secondaryButton"
                    type="button"
                    disabled={index === 0}
                    onClick={() => {
                      const commands = [...editor.commands];
                      [commands[index - 1], commands[index]] = [commands[index], commands[index - 1]];
                      updateEditor({ commands });
                    }}
                  >
                    Up
                  </button>
                  <button
                    className="secondaryButton"
                    type="button"
                    disabled={index === editor.commands.length - 1}
                    onClick={() => {
                      const commands = [...editor.commands];
                      [commands[index], commands[index + 1]] = [commands[index + 1], commands[index]];
                      updateEditor({ commands });
                    }}
                  >
                    Down
                  </button>
                  <button
                    className="dangerButton"
                    type="button"
                    onClick={() =>
                      updateEditor({
                        commands: editor.commands.filter((_, commandIndex) => commandIndex !== index),
                      })
                    }
                  >
                    Remove
                  </button>
                </div>
              ))}
            </div>

            <div className="editorSubsection">
              <h3>Workspace</h3>
              <div className="formGrid">
                <label>
                  <span>Terminal app</span>
                  <select
                    value={editor.workspace.terminalApp}
                    onChange={(event) =>
                      updateEditorWorkspace("terminalApp", event.target.value)
                    }
                  >
                    <option value="">unset</option>
                    <option value="terminal">terminal</option>
                    <option value="iterm">iterm</option>
                    <option value="iterm2">iterm2</option>
                  </select>
                </label>
                <label>
                  <span>Command</span>
                  <input
                    value={editor.workspace.terminalCommand}
                    onChange={(event) =>
                      updateEditorWorkspace("terminalCommand", event.target.value)
                    }
                    placeholder="cd {root} && nvim ."
                  />
                </label>
                <label>
                  <span>Reuse existing</span>
                  <select
                    value={editor.workspace.terminalReuseExisting}
                    onChange={(event) =>
                      updateEditorWorkspace("terminalReuseExisting", event.target.value)
                    }
                  >
                    <option value="">unset</option>
                    <option value="true">true</option>
                    <option value="false">false</option>
                  </select>
                </label>
                <label>
                  <span>Open mode</span>
                  <select
                    value={editor.workspace.terminalOpenMode}
                    onChange={(event) =>
                      updateEditorWorkspace("terminalOpenMode", event.target.value)
                    }
                  >
                    <option value="">unset</option>
                    <option value="tab">tab</option>
                    <option value="window">window</option>
                  </select>
                </label>
                <label>
                  <span>Profile</span>
                  <input
                    value={editor.workspace.terminalProfile}
                    onChange={(event) =>
                      updateEditorWorkspace("terminalProfile", event.target.value)
                    }
                  />
                </label>
                <label>
                  <span>Window bounds</span>
                  <input
                    value={editor.workspace.terminalWindowBounds}
                    onChange={(event) =>
                      updateEditorWorkspace("terminalWindowBounds", event.target.value)
                    }
                    placeholder="100,80,1500,950"
                  />
                </label>
                <label>
                  <span>Browser</span>
                  <input
                    value={editor.workspace.browserApp}
                    onChange={(event) =>
                      updateEditorWorkspace("browserApp", event.target.value)
                    }
                  />
                </label>
                <label>
                  <span>File manager</span>
                  <input
                    value={editor.workspace.fileManagerApp}
                    onChange={(event) =>
                      updateEditorWorkspace("fileManagerApp", event.target.value)
                    }
                  />
                </label>
              </div>
            </div>

            <div className="buttonRow">
              <button
                type="button"
                disabled={submittingProjectRegistry || !editorDirty}
                onClick={() => void handleSaveProjectRegistry()}
              >
                {submittingProjectRegistry ? "Submitting..." : "Save"}
              </button>
              <button
                className="secondaryButton"
                type="button"
                disabled={submittingProjectRegistry}
                onClick={handleCancelProjectRegistry}
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      </section>
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
              {approval.category || approval.risk_level ? (
                <p>
                  {[approval.category, approval.risk_level].filter(Boolean).join(" / ")}
                </p>
              ) : null}
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

function activityIcon(type: string | undefined) {
  switch (type) {
    case "project_command":
      return "CMD";
    case "terminal":
      return "TERM";
    case "browser_session_open":
    case "browser_session_close":
    case "repo_open":
      return "WEB";
    case "git":
      return "GIT";
    case "scheduler_execution":
      return "TASK";
    case "project_backup_created":
    case "project_backup_restored":
    case "project_backup_deleted":
      return "BKP";
    case "project_switch":
      return "PROJ";
    default:
      return "ACT";
  }
}

function replayAction(activity: Activity) {
  const metadata = activity.metadata ?? {};
  const replay = asRecord(metadata.replay);
  const explicitAction = asText(replay?.action);
  if (
    [
      "run_project_command",
      "run_project_command_visible",
      "open_project_repo",
      "open_project_repo_in_browser",
      "set_current_project",
    ].includes(explicitAction)
  ) {
    return explicitAction;
  }

  switch (activity.activity_type) {
    case "project_command":
      return metadata.command_key ? "run_project_command" : "";
    case "terminal":
      return metadata.command_key ? "run_project_command_visible" : "";
    case "project_switch":
      return metadata.project ? "set_current_project" : "";
    case "repo_open":
      return metadata.project
        ? metadata.mode
          ? "open_project_repo_in_browser"
          : "open_project_repo"
        : "";
    default:
      return "";
  }
}

function metadataSummary(activity: Activity) {
  const metadata = activity.metadata ?? {};
  const project = asRecord(metadata.project);
  const terminal = asText(metadata.terminal_type);
  const returncode = metadata.returncode;
  const entries: { label: string; value: string }[] = [];

  if (project) {
    const projectName = asText(project.name, asText(project.id));
    if (projectName) {
      entries.push({ label: "Project", value: projectName });
    }
  } else {
    const projectName = asText(metadata.project);
    if (projectName) {
      entries.push({ label: "Project", value: projectName });
    }
  }

  const command = asText(metadata.command_key);
  if (command) {
    entries.push({ label: "Command", value: command });
  }

  const url = asText(metadata.url);
  if (url) {
    entries.push({ label: "URL", value: url });
  }

  const mode = asText(metadata.mode);
  if (mode) {
    entries.push({ label: "Mode", value: mode });
  }

  const filename = asText(metadata.filename);
  if (filename) {
    entries.push({ label: "Backup", value: filename });
  }

  const projectCount = metadata.project_count;
  if (typeof projectCount === "number" || typeof projectCount === "string") {
    entries.push({ label: "Projects", value: String(projectCount) });
  }

  if (terminal) {
    entries.push({ label: "Terminal", value: terminal });
  }

  if (typeof returncode === "number" || typeof returncode === "string") {
    entries.push({ label: "Return code", value: String(returncode) });
  }

  return entries;
}

function ActivityTab() {
  const [activities, setActivities] = useState<Activity[]>([]);
  const [loading, setLoading] = useState(true);
  const [clearing, setClearing] = useState(false);
  const [replayingId, setReplayingId] = useState("");
  const [inlineApproval, setInlineApproval] = useState<Approval | null>(null);
  const [approvalActionId, setApprovalActionId] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function loadActivity() {
    try {
      setError("");
      setLoading(true);
      const [activityResponse, approval] = await Promise.all([
        getActivity(),
        fetchInlineApproval(
          (item) =>
            item.action === "clear_activity_history" ||
            [
              "run_project_command",
              "run_project_command_visible",
              "open_project_repo",
              "open_project_repo_in_browser",
              "set_current_project",
            ].includes(item.action ?? ""),
        ),
      ]);
      setActivities(activityResponse.activities);
      setInlineApproval(approval);
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setLoading(false);
    }
  }

  async function handleClear() {
    setError("");
    setMessage("");
    setClearing(true);
    try {
      const response = await clearActivityHistory();
      setMessage(response.message);
      const pendingApproval = await fetchInlineApproval(
        (approval) =>
          approval.id === response.data?.approval_id ||
          approval.action === "clear_activity_history",
      );
      setInlineApproval(pendingApproval);
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setClearing(false);
    }
  }

  async function handleReplay(activity: Activity) {
    const id = activity.id ?? "";
    if (!id) {
      return;
    }

    setError("");
    setMessage("");
    setReplayingId(id);
    try {
      const response = await replayActivity(id);
      setMessage(response.message);
      const pendingApproval = await fetchInlineApproval(
        (approval) =>
          approval.id === response.data?.approval_id ||
          approval.action === response.data?.action,
      );
      setInlineApproval(pendingApproval);
      await loadActivity();
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setReplayingId("");
    }
  }

  async function handleApprovalAction(id: string, action: ApprovalAction) {
    setApprovalActionId(id);
    setError("");
    setMessage("");
    try {
      const response = await resolveInlineApproval(id, action);
      setMessage(response.message);
      setInlineApproval(null);
      await loadActivity();
    } catch (currentError) {
      setError(getErrorMessage(currentError));
    } finally {
      setApprovalActionId("");
    }
  }

  useEffect(() => {
    void loadActivity();
  }, []);

  return (
    <section className="panel">
      <div className="panelHeader">
        <div>
          <h1>Activity</h1>
          <p>Execution history for completed Void actions.</p>
        </div>
        <div className="buttonRow panelActions">
          <button
            className="secondaryButton"
            type="button"
            onClick={() => void loadActivity()}
          >
            Refresh
          </button>
          <button
            className="dangerButton"
            type="button"
            disabled={clearing}
            onClick={() => void handleClear()}
          >
            {clearing ? "Requesting..." : "Clear history"}
          </button>
        </div>
      </div>

      {error ? <div className="error">{error}</div> : null}
      {message ? <div className="notice">{message}</div> : null}
      {inlineApproval ? (
        <InlineApprovalCard
          approval={inlineApproval}
          resolving={approvalActionId === inlineApproval.id}
          onResolve={handleApprovalAction}
        />
      ) : null}
      {loading ? <EmptyState>Loading activity...</EmptyState> : null}
      {!loading && activities.length === 0 ? (
        <EmptyState>No activity history.</EmptyState>
      ) : null}

      <div className="activityList">
        {activities.map((activity, index) => {
          const action = replayAction(activity);
          const id = activity.id ?? "";
          const summary = metadataSummary(activity);
          const replayDisabled = !action || !id || replayingId === id;
          const replayTitle = action ? "Replay activity" : "Replay not supported";
          return (
            <article className="activityItem" key={id || index}>
              <div className="activityIcon">{activityIcon(activity.activity_type)}</div>
              <div className="activityBody">
                <div className="cardTopline">
                  <span>{activity.timestamp ?? "unknown time"}</span>
                  <span className={`activityStatus ${activity.status ?? ""}`}>
                    {activity.status ?? "unknown"}
                  </span>
                </div>
                <h2>{activity.summary || "Untitled activity"}</h2>
                <div className="activityType">{activity.activity_type ?? "unknown"}</div>
                <div className="buttonRow">
                  <button
                    className="secondaryButton"
                    type="button"
                    disabled={replayDisabled}
                    onClick={() => void handleReplay(activity)}
                    title={replayTitle}
                  >
                    {replayingId === id ? "Requesting..." : "Replay"}
                  </button>
                </div>
                {summary.length ? (
                  <dl className="activityMetadataSummary">
                    {summary.map((item) => (
                      <div key={item.label}>
                        <dt>{item.label}</dt>
                        <dd>{item.value}</dd>
                      </div>
                    ))}
                  </dl>
                ) : null}
                <JsonBlock value={activity.metadata ?? {}} />
              </div>
            </article>
          );
        })}
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
  if (tab === "browser") {
    return <BrowserTab />;
  }
  if (tab === "git") {
    return <GitTab />;
  }
  if (tab === "project") {
    return <ProjectTab />;
  }
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
  if (tab === "activity") {
    return <ActivityTab />;
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
