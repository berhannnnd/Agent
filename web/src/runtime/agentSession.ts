import { createMemo, createSignal } from "solid-js";
import type { ChatMessage, Role, RuntimeEvent, RuntimeEventKind, RuntimeEventStatus } from "../types";

const welcome: ChatMessage = {
  id: 1,
  role: "assistant",
  content: "目标给我。我会组织上下文、工具和步骤，把它推进到结果。"
};

export function createAgentSession() {
  const [baseUrl, setBaseUrl] = createSignal(window.location.origin);
  const [token, setToken] = createSignal("");
  const [provider, setProvider] = createSignal("openai-chat");
  const [model, setModel] = createSignal("");
  const [modelBaseUrl, setModelBaseUrl] = createSignal("");
  const [apiKey, setApiKey] = createSignal("");
  const [systemPrompt, setSystemPrompt] = createSignal("You are a precise, helpful agent.");
  const [enabledTools, setEnabledTools] = createSignal("");
  const [streaming, setStreaming] = createSignal(true);
  const [input, setInput] = createSignal("");
  const [messages, setMessages] = createSignal<ChatMessage[]>([welcome]);
  const [activity, setActivity] = createSignal<RuntimeEvent[]>(seedActivity());
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
      push("assistant", data.data?.content || "(empty response)");
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
    if (eventType === "tool_start") record("tool", "Tool call", data.name || data.payload?.name || "tool", "running");
    else if (eventType === "tool_result") record("tool", "Tool result", data.name || data.payload?.name || "tool", "done");
    else if (eventType === "code_start") record("code", "Code execution", data.payload?.language || "runtime code", "running");
    else if (eventType === "web_search") record("search", "Web search", data.payload?.query || data.query || "search", "running");
    else if (eventType === "browser_action") record("browser", "Browser action", data.payload?.action || "browser step", "running");
    else if (eventType === "error") {
      removeMessage(assistantId);
      push("error", data.payload?.message || data.message || "stream error");
      record("error", "Stream error", data.payload?.message || data.message || "stream error", "error");
    } else {
      record("stream", eventType, dataText || chunk, "done");
    }
  };

  const payload = (message: string) => compact({
    message,
    provider: provider(),
    model: model(),
    base_url: modelBaseUrl(),
    api_key: apiKey(),
    system_prompt: systemPrompt(),
    enabled_tools: toolList()
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
    apiKey, setApiKey, systemPrompt, setSystemPrompt, enabledTools, setEnabledTools, streaming, setStreaming,
    input, setInput, messages, activity, busy, health, latency, canSend, toolList, send, clear, checkHealth
  };
}

function seedActivity(): RuntimeEvent[] {
  return [
    { id: 101, kind: "search", title: "Web search", detail: "Standby for external research", status: "queued", time: "--:--:--" },
    { id: 102, kind: "tool", title: "Tool call", detail: "Waiting for tool selection", status: "queued", time: "--:--:--" },
    { id: 103, kind: "code", title: "Code execution", detail: "Sandbox ready", status: "queued", time: "--:--:--" }
  ];
}

function createId() {
  return Date.now() + Math.floor(Math.random() * 1000);
}

function timeLabel() {
  return new Date().toLocaleTimeString([], { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function splitCsv(value: string) {
  return value.split(",").map((item) => item.trim()).filter(Boolean);
}

function compact(payload: Record<string, unknown>) {
  return Object.fromEntries(Object.entries(payload).filter(([, value]) => Array.isArray(value) ? value.length > 0 : value !== undefined && value !== null && value !== ""));
}

function safeJson(value: string): any {
  try {
    return JSON.parse(value);
  } catch {
    return { payload: { message: value } };
  }
}

function errorText(error: unknown) {
  return error instanceof Error ? error.message : String(error);
}
