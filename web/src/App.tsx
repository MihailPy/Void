import { useEffect, useState } from "react";
import {
  Approval,
  BrowserSession,
  Capability,
  ClarificationRequest,
  HealthResponse,
  MemoryResponse,
  Project,
  SchedulerStatusResponse,
  ScheduledTask,
  Skill,
  approve,
  clickBrowserSession,
  clickBrowserSelector,
  clearStoredToken,
  closeAllBrowserSessions,
  closeBrowserSession,
  createGitCommit,
  createTask,
  deleteTask,
  describeCurrentProject,
  disableTask,
  enableTask,
  extractBrowserText,
  fillBrowserSession,
  fillBrowserSelector,
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
  health,
  listBrowserSessions,
  openBrowserSession,
  openProjectRepo,
  reject,
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
  suggestGitCommitMessage,
  waitForBrowserSession,
  waitForBrowserSelector,
} from "./api";

type Tab =
  | "chat"
  | "browser"
  | "git"
  | "project"
  | "approvals"
  | "tasks"
  | "capabilities"
  | "skills"
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
            ["Terminal type", terminal?.terminal_type],
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
  const [description, setDescription] = useState("");
  const [projectInput, setProjectInput] = useState("Void");
  const [timeoutSeconds, setTimeoutSeconds] = useState(120);
  const [repoOpenMode, setRepoOpenMode] = useState<"visible" | "headless">("visible");
  const [inlineApproval, setInlineApproval] = useState<Approval | null>(null);
  const [inlineClarification, setInlineClarification] =
    useState<ClarificationRequest | null>(null);
  const [clarificationAnswer, setClarificationAnswer] = useState("");
  const [approvalActionId, setApprovalActionId] = useState("");
  const [loading, setLoading] = useState(true);
  const [setting, setSetting] = useState(false);
  const [runningCommand, setRunningCommand] = useState("");
  const [commandResult, setCommandResult] = useState<StructuredResult | null>(null);
  const [message, setMessage] = useState<StructuredResult | null>(null);
  const [error, setError] = useState("");

  async function loadProjectContext() {
    try {
      setError("");
      setLoading(true);
      const [projectsResponse, descriptionResponse, commandsResponse] = await Promise.all([
        getProjects(),
        describeCurrentProject(),
        getProjectCommands(),
      ]);
      const clarificationResponse = await getClarification();
      setProjects(projectsResponse.projects);
      setCurrentProjectState(descriptionResponse.project);
      setProjectCommands(commandsResponse.commands);
      setProjectCommandCwd(commandsResponse.cwd);
      setDescription(descriptionResponse.description);
      setInlineClarification(normalizeClarification(clarificationResponse.pending));
      const pendingApproval = await fetchInlineApproval(
        (approval) =>
          approval.action === "set_current_project" ||
          approval.action === "run_project_command" ||
          approval.action === "run_project_command_visible" ||
          approval.action === "open_project_repo_in_browser",
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

  async function handleApprovalAction(id: string, action: ApprovalAction) {
    setApprovalActionId(id);
    setError("");
    setMessage(null);
    const approvedAction = inlineApproval?.action;
    try {
      const response = await resolveInlineApproval(id, action);
      if (
        action === "approve" &&
        (approvedAction === "run_project_command" ||
          approvedAction === "run_project_command_visible" ||
          approvedAction === "open_project_repo_in_browser")
      ) {
        setCommandResult(toStructuredResult(response));
      } else {
        setMessage(toStructuredResult(response));
      }
      setInlineApproval(null);
      await loadProjectContext();
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
            approval.action === "open_project_repo_in_browser",
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
        <h2>Known Projects</h2>
        <div className="cardGrid">
          {projects.length === 0 ? (
            <EmptyState>No projects configured.</EmptyState>
          ) : (
            projects.map((project) => (
              <article className="card" key={project.id ?? project.name}>
                <div className="cardTopline">
                  <span>{project.id}</span>
                  <span>{project.root_path}</span>
                </div>
                <h2>{project.name}</h2>
                <div className="field">
                  <span>Repo URL</span>
                  <p>{project.repo_url || "none"}</p>
                </div>
                <div className="field">
                  <span>Aliases</span>
                  <p>{project.aliases?.join(", ") || "none"}</p>
                </div>
                <div className="field">
                  <span>Command keys</span>
                  <p>
                    {project.commands
                      ? Object.keys(project.commands).sort().join(", ") || "none"
                      : "none"}
                  </p>
                </div>
              </article>
            ))
          )}
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
