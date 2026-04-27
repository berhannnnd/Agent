# Agent Runtime Design

## Goal

Build a fresh agent runtime under `agent` that supports multiple model protocols, streaming, function tools, MCP tools, skill manifests, parallel tool execution, CLI chat, and FastAPI chat/SSE endpoints.

## Scope

The new runtime is the source of truth. The old `gateway/shared/llm` client is not preserved as a compatibility layer and should not be used by CLI or API paths.

## Architecture

The runtime uses a canonical schema for messages, content blocks, model responses, stream events, tool calls, and tool results. Provider adapters convert between canonical schema and provider wire protocols for OpenAI Chat Completions, OpenAI Responses, Claude Messages, and Gemini GenerateContent.

Tools are loaded into a single registry from plain Python functions, MCP servers, and skill manifests. Tool calls from one model response execute concurrently, then results are appended to the conversation in canonical order before the next model call.

The CLI and FastAPI routes both call the same `AgentSession` and `AgentRuntime` implementation. Non-streaming routes return the final answer and trace. Streaming routes emit normalized SSE events.

Runtime internals are split by responsibility:

- `PromptCompiler` converts state into provider-neutral model requests.
- `ContextWindowManager` owns session context fitting.
- `RuntimeState` tracks messages, pending tool calls, tool results, events, and loop iteration.
- `ToolOrchestrator` executes tool calls and formats tool result messages.
- `ToolPermissionPolicy` gates tool calls before execution.
- `CheckpointStore` persists resumable nodes such as model responses with pending tool calls and completed tool-result batches.

## Interfaces

- `make dev`: starts streaming terminal chat.
- `POST /api/v1/agent/chat`: returns final answer, messages, tool results, and runtime events.
- `POST /api/v1/agent/chat/stream`: returns SSE events for model deltas, tool activity, final answer, and errors.

## Provider Protocols

- `openai-chat`: OpenAI-compatible `/chat/completions`.
- `openai-responses`: OpenAI `/responses`.
- `claude-messages`: Anthropic Claude Messages.
- `gemini`: Google Gemini GenerateContent.

Each provider exposes `complete()` and `stream()`. Streaming event support is normalized even when providers use different wire event names.

## Tooling

Plain tools are registered as JSON-schema function tools. MCP tools are discovered through Python MCP SDK stdio sessions and registered with `mcp_<server>_<tool>` names. Skill manifests contribute prompt fragments and enabled tool names.

## Safety

Tool execution errors and denied tool calls are returned to the model as error tool results instead of crashing the runtime. The loop has a configurable max iteration count to prevent infinite tool-call cycles. Checkpoints allow a run to resume from pending tool calls after an interruption.
