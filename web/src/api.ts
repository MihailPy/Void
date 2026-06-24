const API_BASE_URL =
  import.meta.env.VITE_VOID_API_URL ?? "http://127.0.0.1:8000";

const TOKEN_STORAGE_KEY = "void_api_token";

export type HealthResponse = {
  ok: boolean;
  service: string;
  version: string;
};

export type ChatResponse = {
  ok: boolean;
  response: string;
};

export type Skill = {
  name?: string;
  description?: string;
  keywords?: string[];
};

export type SkillsResponse = {
  ok: boolean;
  skills: Skill[];
};

export type Capability = {
  id?: string;
  name?: string;
  status?: string;
  description?: string | null;
  problem?: string | null;
  reason?: string | null;
  created_at?: string;
  updated_at?: string;
};

export type CapabilitiesResponse = {
  ok: boolean;
  installed: Capability[];
  requested: Capability[];
  rejected: Capability[];
};

export type Approval = {
  id?: string;
  action?: string;
  arguments?: Record<string, unknown>;
  reason?: string;
  category?: string;
  risk_level?: string;
  created_at?: string;
};

export type ApprovalsResponse = {
  ok: boolean;
  pending: Approval[];
};

export type ApprovalActionResponse = {
  ok: boolean;
  message: string;
};

export type ScheduledTask = {
  id?: string;
  title?: string;
  prompt?: string;
  schedule_type?: "once" | "interval" | "daily" | string;
  schedule_value?: Record<string, unknown>;
  enabled?: boolean;
  created_at?: string;
  updated_at?: string;
  last_run_at?: string | null;
  next_run_at?: string | null;
};

export type ScheduledTasksResponse = {
  ok: boolean;
  tasks: ScheduledTask[];
};

export type SchedulerStatusResponse = {
  ok: boolean;
  enabled: boolean;
  running: boolean;
  interval_seconds: number;
};

export type SchedulerRunOnceResponse = {
  ok: boolean;
  results: Array<Record<string, unknown>>;
};

export type CreateScheduledTaskRequest = {
  title: string;
  prompt: string;
  schedule_type: "once" | "interval" | "daily";
  schedule_value: Record<string, unknown>;
};

export type BrowserTaskRequest = {
  url: string;
  instruction: string;
};

export type BrowserSelectorRequest = {
  url: string;
  selector: string;
};

export type BrowserFillRequest = BrowserSelectorRequest & {
  value: string;
};

export type BrowserWaitRequest = BrowserSelectorRequest & {
  timeout_ms?: number;
};

export type GitCommitRequest = {
  message: string;
};

export type MemoryResponse = {
  ok: boolean;
  content: string;
};

type ApiErrorResponse = {
  ok: false;
  error: string;
};

function isApiErrorResponse(data: unknown): data is ApiErrorResponse {
  return (
    typeof data === "object" &&
    data !== null &&
    "ok" in data &&
    data.ok === false &&
    "error" in data &&
    typeof data.error === "string"
  );
}

export function getStoredToken() {
  return localStorage.getItem(TOKEN_STORAGE_KEY) ?? "";
}

export function setStoredToken(token: string) {
  localStorage.setItem(TOKEN_STORAGE_KEY, token);
}

export function clearStoredToken() {
  localStorage.removeItem(TOKEN_STORAGE_KEY);
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const token = path === "/health" ? "" : getStoredToken().trim();
  const headers = new Headers(options?.headers);
  if (!headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });
  const data = (await response.json()) as unknown;

  if (!response.ok || isApiErrorResponse(data)) {
    if (response.status === 401) {
      throw new Error("Unauthorized. Check your API token.");
    }
    throw new Error(
      isApiErrorResponse(data)
        ? data.error
        : `Request failed with ${response.status}`,
    );
  }

  return data as T;
}

export function health() {
  return request<HealthResponse>("/health");
}

export function sendChatMessage(message: string) {
  return request<ChatResponse>("/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}

export function getSkills() {
  return request<SkillsResponse>("/skills");
}

export function getCapabilities() {
  return request<CapabilitiesResponse>("/capabilities");
}

export function getApprovals() {
  return request<ApprovalsResponse>("/approvals");
}

export function approve(id: string) {
  return request<ApprovalActionResponse>(`/approvals/${id}/approve`, {
    method: "POST",
  });
}

export function reject(id: string) {
  return request<ApprovalActionResponse>(`/approvals/${id}/reject`, {
    method: "POST",
  });
}

export function getTasks() {
  return request<ScheduledTasksResponse>("/tasks");
}

export function getSchedulerStatus() {
  return request<SchedulerStatusResponse>("/scheduler/status");
}

export function runDueTasksNow() {
  return request<SchedulerRunOnceResponse>("/scheduler/run-once", {
    method: "POST",
  });
}

export function createTask(payload: CreateScheduledTaskRequest) {
  return request<ApprovalActionResponse>("/tasks", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function runTask(id: string) {
  return request<ApprovalActionResponse>(`/tasks/${id}/run`, {
    method: "POST",
  });
}

export function enableTask(id: string) {
  return request<ApprovalActionResponse>(`/tasks/${id}/enable`, {
    method: "POST",
  });
}

export function disableTask(id: string) {
  return request<ApprovalActionResponse>(`/tasks/${id}/disable`, {
    method: "POST",
  });
}

export function deleteTask(id: string) {
  return request<ApprovalActionResponse>(`/tasks/${id}`, {
    method: "DELETE",
  });
}

export function getBrowserTitle(url: string) {
  return request<ApprovalActionResponse>("/browser/title", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export function extractBrowserText(url: string) {
  return request<ApprovalActionResponse>("/browser/text", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export function getBrowserLinks(url: string) {
  return request<ApprovalActionResponse>("/browser/links", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export function getBrowserScreenshot(url: string) {
  return request<ApprovalActionResponse>("/browser/screenshot", {
    method: "POST",
    body: JSON.stringify({ url }),
  });
}

export function runBrowserTask(payload: BrowserTaskRequest) {
  return request<ApprovalActionResponse>("/browser/task", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function clickBrowserSelector(payload: BrowserSelectorRequest) {
  return request<ApprovalActionResponse>("/browser/click", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function fillBrowserSelector(payload: BrowserFillRequest) {
  return request<ApprovalActionResponse>("/browser/fill", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function submitBrowserSelector(payload: BrowserSelectorRequest) {
  return request<ApprovalActionResponse>("/browser/submit", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function waitForBrowserSelector(payload: BrowserWaitRequest) {
  return request<ApprovalActionResponse>("/browser/wait", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getGitStatus() {
  return request<ApprovalActionResponse>("/git/status");
}

export function getGitDiff() {
  return request<ApprovalActionResponse>("/git/diff");
}

export function getGitStagedDiff() {
  return request<ApprovalActionResponse>("/git/diff/staged");
}

export function getGitLog() {
  return request<ApprovalActionResponse>("/git/log");
}

export function getGitBranch() {
  return request<ApprovalActionResponse>("/git/branch");
}

export function suggestGitCommitMessage() {
  return request<ApprovalActionResponse>("/git/suggest-commit-message");
}

export function createGitCommit(payload: GitCommitRequest) {
  return request<ApprovalActionResponse>("/git/commit", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function getProjectMemory() {
  return request<MemoryResponse>("/memory/project");
}

export function getFactsMemory() {
  return request<MemoryResponse>("/memory/facts");
}

export function getSessionMemory() {
  return request<MemoryResponse>("/memory/session");
}
