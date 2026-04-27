import type { ChatMessage, RuntimeEvent, ToolApprovalRequest } from "../types";

export const welcome: ChatMessage = {
  id: 1,
  role: "assistant",
  content: "目标给我。我会组织上下文、工具和步骤，把它推进到结果。"
};

export function seedActivity(): RuntimeEvent[] {
  return [
    { id: 101, kind: "search", title: "Web search", detail: "Standby for external research", status: "queued", time: "--:--:--" },
    { id: 102, kind: "tool", title: "Tool call", detail: "Waiting for tool selection", status: "queued", time: "--:--:--" },
    { id: 103, kind: "approval", title: "Tool approval", detail: "No pending approvals", status: "queued", time: "--:--:--" }
  ];
}

export function approvalFromEvent(event: any, fallbackRunId: string): ToolApprovalRequest {
  const call = event.payload?.tool_call || {};
  return {
    approvalId: event.payload?.approval_id || call.id || call.name || event.name || "tool",
    runId: event.payload?.run_id || fallbackRunId,
    toolName: call.name || event.name || "tool",
    arguments: call.arguments || {},
    reason: event.payload?.permission?.reason || "Tool approval required"
  };
}

export function mergeApproval(current: ToolApprovalRequest[], request: ToolApprovalRequest) {
  if (current.some((item) => item.approvalId === request.approvalId)) return current;
  return [...current, request];
}

export function createId() {
  return Date.now() + Math.floor(Math.random() * 1000);
}

export function timeLabel() {
  return new Date().toLocaleTimeString([], { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

export function splitCsv(value: string) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

export function compact(payload: Record<string, unknown>) {
  return Object.fromEntries(
    Object.entries(payload).filter(([, value]) => Array.isArray(value) ? value.length > 0 : value !== undefined && value !== null && value !== "")
  );
}

export function safeJson(value: string): any {
  try {
    return JSON.parse(value);
  } catch {
    return { payload: { message: value } };
  }
}

export function errorText(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}
