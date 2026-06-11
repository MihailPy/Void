const API_BASE_URL =
  import.meta.env.VITE_VOID_API_URL ?? "http://127.0.0.1:8000";

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

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
    ...options,
  });
  const data = (await response.json()) as unknown;

  if (!response.ok || isApiErrorResponse(data)) {
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

export function getProjectMemory() {
  return request<MemoryResponse>("/memory/project");
}

export function getFactsMemory() {
  return request<MemoryResponse>("/memory/facts");
}

export function getSessionMemory() {
  return request<MemoryResponse>("/memory/session");
}
