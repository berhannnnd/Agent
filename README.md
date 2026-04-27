# Agents

Agents is a Python-first agent system organized as a reusable agent core plus service and UI adapters.

The project boundary is intentionally strict:

```text
web  -> gateway HTTP/SSE -> agent
cli  -> agent

gateway -> agent
agent   -> no gateway, FastAPI, or UI dependency
```

`agent/` is the core SDK/kernel. It defines agents, model protocols, context assembly, tools, permissions, runtime loops, checkpoints, run records, workspaces, skills, and MCP integration.

`gateway/` is the service adapter. It exposes the agent core over HTTP/SSE, owns request/response schemas, service concurrency, run lifecycle tracking, and future auth/session persistence.

`cli/` and `web/` are interfaces. They should not implement agent logic.

## Current Capabilities

- Multi-provider model layer: OpenAI Chat Completions, OpenAI Responses, Claude Messages, Gemini.
- Provider-neutral streaming protocol for text deltas, reasoning deltas, tool call deltas, usage, and final messages.
- Agent runtime with tool-call loop, streaming, hook points, checkpoint/resume support, and max-iteration guard.
- Context system with layered fragments: system, runtime policy, workspace instructions, skills, memory, tool hints, task context.
- Tool registry with concurrent execution, timeout handling, error-to-tool-result conversion, and MCP stdio loading.
- `AgentSpec` definition layer for model overrides, enabled tools, skills, workspace scope, tool permissions, memory profile, and metadata.
- Tool approval flow with `auto`, `ask`, and `deny` modes, checkpoint-backed pause/resume, run status `awaiting_approval`, and web Approve/Deny controls.
- Workspace isolation under `tenant_id / user_id / agent_id / workspace_id`.
- Run tracking through `RunStore`, backed by memory, local JSON files, or SQLite.
- SQLite persistence for run records, runtime events, checkpoints, approval audit, and trace spans.
- Long-term data stores for tenants/users, agent profiles, workspace records, memories, and credential references.
- Traceable run timelines through `agent.tracing`, with separate approval audit records through `agent.audit`.
- Gateway chat APIs return `run_id`; streaming emits a `run_created` event before model/tool events.

## Repository Layout

```text
agent/
  assembly/       Build AgentSession from settings + AgentSpec
  audit/          Approval audit records and audit stores
  config/         Model/provider config resolution
  context/        ContextPack, ContextBuilder, windowing, request compilation
  definitions/    AgentSpec, AgentProfile, model/workspace/permission definitions
  hooks/          Runtime hooks and hook composition
  identity/       Tenant/user/agent identity references and identity stores
  integrations/   Skills and MCP loading
  memory/         MemoryRecord and memory stores
  models/         ModelClient, adapters, protocol, transports, retry, errors
  orchestration/  Future multi-agent planner/router/supervisor boundary
  persistence/    Shared local persistence primitives
  runs/           RunRecord, RunStore, memory/file/sqlite stores
  runtime/        Agent loop, session, state, events, turns, checkpoints
  security/       Tool permission rules, credential refs, future safety boundaries
  skills/         Skill manifest and prompt fragment loading
  storage/        Workspace allocation and workspace records
  tools/          ToolRegistry and MCP tool provider
  tracing/        Run/tool/model/approval trace spans
  workflows/      Future workflow/DAG boundary
  schema.py       Core message/tool/model/runtime data types

gateway/
  api/            FastAPI routes and HTTP schemas
  auth/           Future auth boundary
  core/           Settings, logging, middleware, exceptions
  services/       Cross-cutting gateway service containers
  sessions/       Gateway run lifecycle service
  streaming/      Future SSE/WebSocket protocol helpers
  static_ui.py    Mounts web/dist at /ui

cli/              Typer terminal interface
web/              SolidJS + Vite browser interface
tests/            Unit and boundary tests
docs/             Architecture notes
```

## Quick Start

```bash
make setup
cp .env.example .env
```

Edit `.env` and configure at least one provider API key and model.

Start the gateway:

```bash
make run
curl http://127.0.0.1:8010/health
```

Start the terminal chat:

```bash
make cli
# or
agents chat --provider openai-chat --model gpt-4o
```

Run tests:

```bash
make test
```

## Configuration

Configuration is loaded through `gateway.core.config.settings`.

| Domain | Env prefix | Common fields |
|---|---|---|
| `settings.agent` | `AGENT_` | `AGENT_PROVIDER`, `AGENT_MAX_TOKENS`, `AGENT_MAX_RETRIES`, `AGENT_ENABLED_TOOLS`, `AGENT_SKILLS`, `AGENT_WORKSPACE_ROOT`, `AGENT_RUN_STORE`, `AGENT_RUN_ROOT`, `AGENT_DB_PATH` |
| `settings.models.openai` | `OPENAI_` | `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_MODEL` |
| `settings.models.openai_responses` | `OPENAI_RESPONSES_` | `OPENAI_RESPONSES_API_KEY`, `OPENAI_RESPONSES_BASE_URL`, `OPENAI_RESPONSES_MODEL` |
| `settings.models.anthropic` | `ANTHROPIC_` | `ANTHROPIC_API_KEY`, `ANTHROPIC_BASE_URL`, `ANTHROPIC_MODEL` |
| `settings.models.gemini` | `GEMINI_` | `GEMINI_API_KEY`, `GEMINI_BASE_URL`, `GEMINI_MODEL` |
| `settings.mcp` | `MCP_` | `MCP_SERVER_NAME`, `MCP_SERVER_COMMAND`, `MCP_CLIENT_TIMEOUT` |

Provider names:

| Provider | Protocol |
|---|---|
| `openai-chat` | OpenAI Chat Completions |
| `openai-responses` | OpenAI Responses API |
| `claude-messages` | Anthropic Claude Messages |
| `gemini` | Gemini Generate Content |

Claude-compatible config prefers project-owned `AGENT_CLAUDE_*` values before falling back to ambient `ANTHROPIC_*` values.

Run records use memory by default. To keep run records as local JSON files:

```bash
AGENT_RUN_STORE=file
AGENT_RUN_ROOT=.agents/runs
```

To persist runs, runtime events, approval checkpoints, approval audit, trace spans, and long-term domain records in one local database:

```bash
AGENT_RUN_STORE=sqlite
AGENT_DB_PATH=.agents/agents.db
```

## HTTP API

Non-streaming:

```bash
curl -X POST http://127.0.0.1:8010/api/v1/agent/chat \
  -H 'Content-Type: application/json' \
  -d '{
    "message": "hello",
    "provider": "openai-chat",
    "model": "gpt-4o"
  }'
```

Response data includes:

```json
{
  "run_id": "run_...",
  "status": "finished",
  "content": "...",
  "messages": [],
  "tool_results": [],
  "events": []
}
```

Streaming:

```bash
curl -N -X POST http://127.0.0.1:8010/api/v1/agent/chat/stream \
  -H 'Content-Type: application/json' \
  -d '{"message":"hello"}'
```

The first SSE event is always `run_created`:

```text
event: run_created
data: {"type":"run_created","name":"run","payload":{"run_id":"run_..."}}
```

Then the stream emits runtime events such as `text_delta`, `reasoning_delta`, `tool_approval_required`, `tool_approval_decision`, `tool_start`, `tool_result`, `error`, and `done`.

Query a run:

```bash
curl http://127.0.0.1:8010/api/v1/agent/runs/run_...
```

The response contains the run scope, status, timestamps, metadata, and recorded runtime events.

Query the trace timeline for the same run:

```bash
curl http://127.0.0.1:8010/api/v1/agent/runs/run_.../trace
```

The response contains ordered trace spans for run/model/tool/approval activity plus approval audit decisions. Trace spans are operational observability; approval audit records are the stable accountability trail.

### Tool Approval

Tool permissions are part of `AgentSpec`, not UI state. Request bodies can set:

```json
{
  "message": "inspect the workspace",
  "permission_profile": "ask",
  "enabled_tools": ["filesystem.read"]
}
```

Modes:

| Mode | Behavior |
|---|---|
| `auto` | Execute allowed tools without pausing. |
| `ask` | Pause before tool execution and emit `tool_approval_required`. |
| `deny` | Return denied tool results without executing tools. |

When a tool requires approval, the run is marked `awaiting_approval` and the runtime checkpoint keeps the pending tool calls. Resume the same run:

```bash
curl -X POST http://127.0.0.1:8010/api/v1/agent/runs/run_.../approval \
  -H 'Content-Type: application/json' \
  -d '{"tool_call_ids":["call_..."],"approved":true}'
```

The web UI uses this endpoint for the Approve/Deny panel. The gateway owns the HTTP flow; `agent/runtime` owns the pause/resume semantics.

## Agent And Run Model

External callers construct an `AgentSpec`. The spec carries:

- model override: provider, model, base URL, API key
- workspace scope: tenant, user, agent, workspace
- enabled tools and skills
- tool permission mode/rules and memory profile names
- metadata

Gateway and CLI convert request/options into `AgentSpec`, then call:

```python
from agent.assembly import create_agent_session, create_agent_session_async
```

Each chat request creates a new run. `run_id` is generated by the gateway run service and passed into `AgentSession.send()` or `AgentSession.stream()`. Runtime checkpoints, gateway run records, trace spans, and approval audit records share that same ID. In file mode, each run is stored as one JSON document under `AGENT_RUN_ROOT`. In SQLite mode, runs, runtime events, checkpoints, trace spans, approval audit records, and long-term domain records share `AGENT_DB_PATH`.

SQLite domain tables:

| Table | Purpose |
|---|---|
| `tenants`, `users` | Identity scope used by later gateway auth. |
| `agent_profiles` | Stored agent definitions without API keys. |
| `workspace_records` | Workspace ownership, path, status, and metadata. |
| `memory_records` | User, agent, workspace, and run-scoped memories. |
| `credential_refs` | References to secrets stored elsewhere; raw secrets are not stored here. |

Defaults for local development:

```text
tenant_id    default
user_id      anonymous
agent_id     default
workspace_id default
run_id       generated per request
```

## Web UI

Build and serve through the gateway:

```bash
cd web && npm run build
make run
```

When `web/dist/` exists, the gateway mounts it at `/ui/` and redirects `/` to `/ui/`.

For frontend development:

```bash
make dev-web
```

## Development Rules

- Put agent logic in `agent/`, not in `gateway/`, `cli/`, or `web/`.
- Put HTTP/session/auth protocol code in `gateway/`.
- Add model providers under `agent/models/adapters/`; keep shared stream semantics in `agent/models/protocol/`.
- Add tools under `agent/tools/` or load them through MCP.
- Add new context sources through `agent/context/sources.py`.
- Add new run persistence backends by implementing `agent.runs.RunStore`; checkpoint, trace, and approval audit storage should stay behind their own store interfaces. Gateway should only choose and call adapters.
- Add identity/auth from gateway login state later; do not trust user-supplied `tenant_id` or `user_id` in cloud mode.
