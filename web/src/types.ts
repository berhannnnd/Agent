export type Role = "user" | "assistant" | "system" | "event" | "error";

export type ChatMessage = {
  id: number;
  role: Role;
  content: string;
};

export type ActivityEventKind = "system" | "stream" | "tool" | "approval" | "code" | "search" | "browser" | "error";
export type ActivityEventStatus = "queued" | "running" | "waiting" | "done" | "error";

export type ActivityEvent = {
  id: number;
  kind: ActivityEventKind;
  title: string;
  detail: string;
  status: ActivityEventStatus;
  time: string;
};

export const modelProtocols = ["openai-chat", "openai-responses", "claude-messages", "gemini"] as const;

export type PermissionMode = "auto" | "ask" | "deny";
export type ApprovalDecision = "allow_once" | "allow_for_run" | "deny";
export type ToolImpact = {
  tool_name?: string;
  risk?: string;
  paths?: string[];
  commands?: string[];
  domains?: string[];
  diff_preview?: string;
  cost_estimate?: Record<string, unknown>;
};

export type ToolApprovalRequest = {
  approvalId: string;
  runId: string;
  toolName: string;
  arguments: Record<string, unknown>;
  reason: string;
  impact: ToolImpact;
};
