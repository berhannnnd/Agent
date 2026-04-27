export type Role = "user" | "assistant" | "system" | "event" | "error";

export type ChatMessage = {
  id: number;
  role: Role;
  content: string;
};

export type RuntimeEventKind = "system" | "stream" | "tool" | "code" | "search" | "browser" | "error";
export type RuntimeEventStatus = "queued" | "running" | "done" | "error";

export type RuntimeEvent = {
  id: number;
  kind: RuntimeEventKind;
  title: string;
  detail: string;
  status: RuntimeEventStatus;
  time: string;
};

export const providers = ["openai-chat", "openai-responses", "claude-messages", "gemini"] as const;
