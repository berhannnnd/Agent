# Agent Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a fresh multi-provider tool-calling agent runtime with CLI and FastAPI/SSE interfaces.

**Architecture:** Canonical schema sits at the center. Provider adapters translate model protocols, tool registry executes calls concurrently, and one runtime powers CLI/API.

**Tech Stack:** Python 3.10+, FastAPI, Typer, Pydantic, stdlib urllib, optional MCP Python SDK/FastMCP.

---

### Task 1: Canonical Schema and Provider Adapters

**Files:**
- Create: `agent/schema.py`
- Create: `agent/providers/adapters.py`
- Create: `agent/providers/client.py`
- Create: `tests/test_agent_providers.py`

- [ ] Write tests for request payload and response parsing for OpenAI Chat, OpenAI Responses, Claude Messages, and Gemini.
- [ ] Implement canonical dataclasses and provider adapters.
- [ ] Implement shared HTTP/SSE transport client.
- [ ] Run `pytest tests/test_agent_providers.py -q`.

### Task 2: Tool Registry, MCP, and Skills

**Files:**
- Create: `agent/tools/registry.py`
- Create: `agent/tools/mcp.py`
- Create: `agent/skills.py`
- Create: `tests/test_agent_tools.py`

- [ ] Write tests for function tool registration, duplicate rejection, parallel execution ordering, MCP tool loading with fake client, and skill manifest loading.
- [ ] Implement async tool registry and executor.
- [ ] Implement MCP provider boundary using Python MCP SDK when installed, with fake-client test seam.
- [ ] Implement skill manifest loader.
- [ ] Run `pytest tests/test_agent_tools.py -q`.

### Task 3: Agent Runtime

**Files:**
- Create: `agent/runtime/`
- Create: `tests/test_agent_runtime.py`

- [ ] Write tests for model-tool-model loop, parallel tool execution, failed tool result handling, max iteration guard, and streaming events.
- [ ] Implement `AgentRuntime` and `AgentSession`.
- [ ] Run `pytest tests/test_agent_runtime.py -q`.

### Task 4: CLI and API Wiring

**Files:**
- Modify: `cli/main.py`
- Modify: `gateway/api/router.py`
- Create: `gateway/api/agent/schemas.py`
- Create: `gateway/api/agent/api_agent.py`
- Modify: `gateway/core/config.py`
- Modify: `.env.example`
- Modify: `requirements/requirements.txt`
- Create/modify tests for CLI and API.

- [ ] Write tests for CLI streaming chat, API non-stream chat, and API SSE event format.
- [ ] Wire CLI/API to `AgentSession`.
- [ ] Add provider and MCP config settings.
- [ ] Run `make test`.

### Task 5: Remove Old LLM Path

**Files:**
- Delete or detach: `gateway/shared/llm/*`
- Update: tests that imported old LLM path.

- [ ] Move tests to new `agent` imports.
- [ ] Remove unused old LLM code.
- [ ] Run `make test`, `python -m compileall -q app tests main.py`, and `git diff --check`.
