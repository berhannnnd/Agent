import { createMemo, createSignal } from "solid-js";
import type {
  ChatMessage,
  PermissionMode,
  Role,
  RuntimeEvent,
  RuntimeEventKind,
  RuntimeEventStatus,
  ToolApprovalRequest
} from "../types";
import { approvalFromEvent, compact, createId, errorText, mergeApproval, safeJson, seedActivity, splitCsv, timeLabel, welcome } from "./sessionUtils";

export function createAgentSession() {
  const [baseUrl, setBaseUrl] = createSignal(window.location.origin);
  const [token, setToken] = createSignal("");
  const [provider, setProvider] = createSignal("openai-chat");
  const [model, setModel] = createSignal("");
  const [modelBaseUrl, setModelBaseUrl] = createSignal("");
  const [apiKey, setApiKey] = createSignal("");
  const [systemPrompt, setSystemPrompt] = createSignal("You are a precise, helpful agent.");
  const [enabledTools, setEnabledTools] = createSignal("");
  const [permissionMode, setPermissionMode] = createSignal<PermissionMode>("ask");
  const [streaming, setStreaming] = createSignal(true);
  const [input, setInput] = createSignal("");
  const [messages, setMessages] = createSignal<ChatMessage[]>([welcome]);
  const [activity, setActivity] = createSignal<RuntimeEvent[]>(seedActivity());
  const [pendingApprovals, setPendingApprovals] = createSignal<ToolApprovalRequest[]>([]);
  const [runId, setRunId] = createSignal("");
  const [busy, setBusy] = createSignal(false);
  const [health, setHealth] = createSignal("unknown");
  const [latency, setLatency] = createSignal<number | null>(null);

  const canSend = createMemo(() => input().trim().length > 0 && !busy());
  const toolList = createMemo(() => splitCsv(enabledTools()));

  const send = async () => {
    const text = input().trim();
    if (!text || busy()) return;
    push("user", text);
    setInput("");
    setActivity([]);
    setPendingApprovals([]);
    setRunId("");
    record("system", "Request received", text, "done");
    if (streaming()) await sendStream(text);
    else await sendChat(text);
  };

  const sendChat = async (text: string) => {
    const started = performance.now();
    setBusy(true);
    const requestId = record("system", "Model request", "POST /api/v1/agent/chat", "running");
    try {
      const response = await fetch(urlFor("/api/v1/agent/chat"), {
        method: "POST",
        headers: headers(),
        body: JSON.stringify(payload(text))
      });
      const data = await response.json();
      setLatency(Math.round(performance.now() - started));
      updateActivity(requestId, { status: response.ok ? "done" : "error", detail: `${response.status} ${response.statusText}` });
      if (!response.ok || data.success === false) {
        push("error", data?.data?.detail || data?.message || `${response.status} ${response.statusText}`);
        record("error", "Request failed", data?.message || "Agent request returned an error", "error");
        return;
      }
      setRunId(data.data?.run_id || "");
      consumeRuntimeEvents(data.data?.events || []);
      if (data.data?.status !== "awaiting_approval") push("assistant", data.data?.content || "(empty response)");
      for (const item of data.data?.tool_results || []) {
        push("event", `${item.name}: ${item.content}`);
        record("tool", "Tool call", `${item.name}: ${item.content}`, "done");
      }
    } catch (error) {
      updateActivity(requestId, { status: "error", detail: errorText(error) });
      push("error", errorText(error));
    } finally {
      setBusy(false);
    }
  };

  const decideApproval = async (request: ToolApprovalRequest, approved: boolean) => {
    setBusy(true);
    const id = record("approval", approved ? "Tool approved" : "Tool denied", request.toolName, "running");
    try {
      const response = await fetch(urlFor(`/api/v1/agent/runs/${request.runId}/approval`), {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ tool_call_ids: [request.approvalId], approved })
      });
      const data = await response.json();
      updateActivity(id, { status: response.ok ? "done" : "error", detail: `${response.status} ${response.statusText}` });
      if (!response.ok || data.success === false) {
        push("error", data?.data?.detail || data?.message || "approval request failed");
        return;
      }
      setPendingApprovals((current) => current.filter((item) => item.approvalId !== request.approvalId));
      consumeRuntimeEvents(data.data?.events || []);
      if (data.data?.status !== "awaiting_approval") push("assistant", data.data?.content || "(empty response)");
    } catch (error) {
      updateActivity(id, { status: "error", detail: errorText(error) });
      push("error", errorText(error));
    } finally {
      setBusy(false);
    }
  };

  const sendStream = async (text: string) => {
    const started = performance.now();
    setBusy(true);
    const assistantId = push("assistant", "");
    const streamId = record("stream", "Streaming response", "Opening event stream", "running");
    try {
      const response = await fetch(urlFor("/api/v1/agent/chat/stream"), {
        method: "POST",
        headers: headers(),
        body: JSON.stringify(payload(text))
      });
      if (!response.body) throw new Error("Streaming is not available in this browser.");
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const chunks = buffer.split("\n\n");
        buffer = chunks.pop() ?? "";
        chunks.forEach((chunk) => handleSseChunk(chunk, assistantId, streamId));
      }
      if (buffer.trim()) handleSseChunk(buffer, assistantId, streamId);
      setLatency(Math.round(performance.now() - started));
      updateActivity(streamId, { status: "done", detail: "Response stream closed" });
    } catch (error) {
      removeMessage(assistantId);
      updateActivity(streamId, { status: "error", detail: errorText(error) });
      push("error", errorText(error));
    } finally {
      setBusy(false);
    }
  };

  const checkHealth = async () => {
    const id = record("system", "Health probe", "GET /health", "running");
    try {
      const response = await fetch(urlFor("/health"), { headers: token().trim() ? { Authorization: `Bearer ${token().trim()}` } : {} });
      setHealth(response.ok ? "online" : "degraded");
      updateActivity(id, { status: response.ok ? "done" : "error", detail: `${response.status} ${response.statusText}` });
    } catch (error) {
      setHealth("offline");
      updateActivity(id, { status: "error", detail: errorText(error) });
    }
  };

  const clear = () => {
    setMessages([]);
    setActivity(seedActivity());
    setLatency(null);
  };

  const handleSseChunk = (chunk: string, assistantId: number, streamId: number) => {
    if (!chunk.trim()) return;
    const eventType = chunk.split("\n").find((line) => line.startsWith("event: "))?.slice(7) || "message";
    const dataText = chunk.split("\n").find((line) => line.startsWith("data: "))?.slice(6);
    const data = dataText ? safeJson(dataText) : {};
    if (eventType === "text_delta") {
      const delta = data.payload?.delta || data.delta || "";
      updateMessage(assistantId, delta, true);
      updateActivity(streamId, { detail: `Streaming text delta: ${delta.length} chars` });
      return;
    }
    if (eventType === "done") {
      updateMessage(assistantId, data.payload?.content || data.content || "");
      return;
    }
    if (eventType === "error") {
      removeMessage(assistantId);
      push("error", data.payload?.message || data.message || "stream error");
    }
    consumeRuntimeEvents([{ type: eventType, name: data.name, payload: data.payload || data }]);
  };

  const consumeRuntimeEvents = (events: any[]) => {
    for (const event of events) {
      if (event.type === "run_created") {
        setRunId(event.payload?.run_id || "");
        continue;
      }
      if (event.type === "tool_approval_required") {
        const request = approvalFromEvent(event, runId());
        setPendingApprovals((current) => mergeApproval(current, request));
        record("approval", "Approval required", request.toolName, "waiting");
        continue;
      }
      if (event.type === "tool_approval_decision") {
        const approved = event.payload?.approved ? "approved" : "denied";
        record("approval", `Tool ${approved}`, event.name || event.payload?.tool_call?.name || "tool", "done");
        continue;
      }
      if (event.type === "tool_start") record("tool", "Tool call", event.name || event.payload?.name || "tool", "running");
      else if (event.type === "tool_result") record("tool", "Tool result", event.name || event.payload?.name || "tool", "done");
      else if (event.type === "code_start") record("code", "Code execution", event.payload?.language || "runtime code", "running");
      else if (event.type === "web_search") record("search", "Web search", event.payload?.query || event.query || "search", "running");
      else if (event.type === "browser_action") record("browser", "Browser action", event.payload?.action || "browser step", "running");
      else if (event.type === "error") record("error", "Stream error", event.payload?.message || event.message || "stream error", "error");
      else record("stream", event.type || "event", JSON.stringify(event.payload || event), "done");
    }
  };

  const payload = (message: string) => compact({
    message,
    provider: provider(),
    model: model(),
    base_url: modelBaseUrl(),
    api_key: apiKey(),
    system_prompt: systemPrompt(),
    enabled_tools: toolList(),
    permission_profile: permissionMode()
  });

  const headers = () => {
    const result: Record<string, string> = { "Content-Type": "application/json" };
    if (token().trim()) result.Authorization = `Bearer ${token().trim()}`;
    return result;
  };

  const urlFor = (path: string) => `${baseUrl().replace(/\/$/, "")}${path}`;
  const push = (role: Role, content: string) => {
    const id = createId();
    setMessages((current) => [...current, { id, role, content }]);
    return id;
  };
  const record = (kind: RuntimeEventKind, title: string, detail: string, status: RuntimeEventStatus) => {
    const id = createId();
    setActivity((current) => [{ id, kind, title, detail, status, time: timeLabel() }, ...current]);
    return id;
  };
  const updateMessage = (id: number, content: string, append = false) => {
    setMessages((current) => current.map((message) => message.id === id ? { ...message, content: append ? `${message.content}${content}` : content } : message));
  };
  const removeMessage = (id: number) => setMessages((current) => current.filter((message) => message.id !== id));
  const updateActivity = (id: number, patch: Partial<RuntimeEvent>) => {
    setActivity((current) => current.map((event) => event.id === id ? { ...event, ...patch } : event));
  };

  return {
    baseUrl, setBaseUrl, token, setToken, provider, setProvider, model, setModel, modelBaseUrl, setModelBaseUrl,
    apiKey, setApiKey, systemPrompt, setSystemPrompt, enabledTools, setEnabledTools, permissionMode, setPermissionMode,
    streaming, setStreaming, input, setInput, messages, activity, pendingApprovals, busy, health, latency, canSend,
    toolList, send, decideApproval, clear, checkHealth
  };
}
