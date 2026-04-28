# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：test_agent_tools.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agent.context.workspace import WorkspaceContext
from agent.governance import SandboxPolicy, describe_tool_impact
from agent.schema import ToolCall
from agent.capabilities.skills import SkillLoader, SkillRegistry
from agent.capabilities.sandbox.local import LocalSandboxProvider
from agent.capabilities.sandbox.types import SandboxCommandResult
from agent.capabilities.tools.builtin.browser import browser_open
from agent.capabilities.tools.mcp import MCPServerConfig, MCPToolDefinition, MCPToolProvider
from agent.capabilities.tools import ToolRuntimeContext, register_builtin_tools
from agent.capabilities.tools.registry import ToolRegistry


def test_tool_registry_registers_specs_and_rejects_duplicates():
    registry = ToolRegistry()
    registry.register(
        "echo",
        "Echo text",
        {"type": "object", "properties": {"text": {"type": "string"}}},
        lambda text: text,
    )

    assert registry.specs()[0].name == "echo"
    with pytest.raises(ValueError):
        registry.register("echo", "Echo again", {}, lambda: "x")


def test_tool_registry_exposes_metadata_in_specs():
    registry = ToolRegistry()
    registry.register("dangerous", "Dangerous", {}, lambda: "ok", metadata={"risk": "high"})

    spec = registry.specs(["dangerous"])[0]

    assert spec.raw["metadata"]["risk"] == "high"


def test_tool_executor_runs_calls_concurrently_and_preserves_order():
    registry = ToolRegistry()
    calls = []

    async def slow(text):
        await asyncio.sleep(0.02)
        calls.append(text)
        return text

    async def fast(text):
        calls.append(text)
        return text

    registry.register("slow", "Slow", {}, slow)
    registry.register("fast", "Fast", {}, fast)

    results = asyncio.run(
        registry.execute_many(
            [
                ToolCall(id="call-1", name="slow", arguments={"text": "first"}),
                ToolCall(id="call-2", name="fast", arguments={"text": "second"}),
            ]
        )
    )

    assert [item.tool_call_id for item in results] == ["call-1", "call-2"]
    assert [item.content for item in results] == ["first", "second"]
    assert calls == ["second", "first"]


def test_tool_executor_converts_failures_to_error_results():
    registry = ToolRegistry()

    def fail():
        raise RuntimeError("broken")

    registry.register("fail", "Fail", {}, fail)

    results = asyncio.run(registry.execute_many([ToolCall(id="call-1", name="fail")]))

    assert results[0].is_error is True
    assert "broken" in results[0].content


class FakeMCPClient:
    def __init__(self):
        self.called = []

    async def list_tools(self):
        return [
            MCPToolDefinition(
                name="search",
                description="Search docs",
                parameters={"type": "object", "properties": {"query": {"type": "string"}}},
            )
        ]

    async def call_tool(self, name, arguments):
        self.called.append((name, arguments))
        return {"answer": arguments["query"]}


def test_mcp_provider_loads_tools_with_server_prefix():
    registry = ToolRegistry()
    client = FakeMCPClient()
    provider = MCPToolProvider(
        client=client,
        server=MCPServerConfig(name="docs", execution_mode="trusted_control_plane"),
    )

    asyncio.run(provider.load_tools(registry))
    result = asyncio.run(registry.execute("mcp_docs_search", {"query": "agents"}))

    assert registry.specs(["mcp_docs_search"])[0].name == "mcp_docs_search"
    assert registry.specs(["mcp_docs_search"])[0].raw["metadata"]["execution_mode"] == "trusted_control_plane"
    assert json.loads(result.content)["answer"] == "agents"
    assert client.called == [("search", {"query": "agents"})]


def test_patch_apply_edits_and_creates_workspace_files(tmp_path: Path):
    workspace = WorkspaceContext(
        tenant_id="default",
        user_id="user-1",
        agent_id="agent-1",
        workspace_id="default",
        root=tmp_path,
        path=tmp_path,
    )
    (tmp_path / "notes.txt").write_text("hello old world\n", encoding="utf-8")
    policy = SandboxPolicy.for_workspace(workspace.path, allow_file_write=True)
    context = ToolRuntimeContext(
        workspace=workspace,
        sandbox=policy,
        sandbox_client=LocalSandboxProvider().acquire(workspace, policy),
    )
    registry = ToolRegistry()
    register_builtin_tools(registry, context)

    result = asyncio.run(
        registry.execute(
            "patch.apply",
            {
                "edits": [{"path": "notes.txt", "old_text": "old", "new_text": "new"}],
                "creates": [{"path": "created.txt", "content": "created\n"}],
            },
        )
    )

    payload = result.raw
    assert result.is_error is False
    assert (tmp_path / "notes.txt").read_text(encoding="utf-8") == "hello new world\n"
    assert (tmp_path / "created.txt").read_text(encoding="utf-8") == "created\n"
    assert [item["path"] for item in payload["files"]] == ["notes.txt", "created.txt"]
    assert "--- a/notes.txt" in payload["diff"]


def test_tool_impact_describes_patch_paths_and_preview():
    call = ToolCall(
        id="call-1",
        name="patch.apply",
        arguments={"edits": [{"path": "app.py", "old_text": "a = 1", "new_text": "a = 2"}]},
    )

    impact = describe_tool_impact(call).to_dict()

    assert impact["risk"] == "medium"
    assert impact["writes_files"] is True
    assert impact["paths"] == ["app.py"]
    assert "a = 2" in impact["diff_preview"]


class FakeBrowserSandbox:
    async def run_command(self, command, timeout_seconds=30.0):
        return SandboxCommandResult(
            command=command,
            exit_code=0,
            stdout=json.dumps(
                {
                    "url": "https://example.com",
                    "path": "artifacts/downloads/page.html",
                    "status": 200,
                    "content_type": "text/html",
                    "bytes": 12,
                    "truncated": False,
                }
            ),
        )


def test_browser_open_uses_sandbox_network_and_process_path():
    policy = SandboxPolicy.for_workspace(
        Path("."),
        allow_file_write=True,
        allow_process=True,
        allow_network=True,
        allowed_commands=("python3",),
    )
    context = SimpleNamespace(sandbox=policy, sandbox_client=FakeBrowserSandbox())

    result = asyncio.run(browser_open(context, "https://example.com", output_path="artifacts/downloads/page.html"))

    assert result["status"] == 200
    assert result["path"] == "artifacts/downloads/page.html"


def test_skill_registry_loads_prompt_fragments_and_tool_names(tmp_path: Path):
    (tmp_path / "skills").mkdir()
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "focus.md").write_text("Focus on {topic}.", encoding="utf-8")
    (tmp_path / "skills" / "focus.json").write_text(
        json.dumps(
            {
                "name": "focus",
                "version": "1.0.0",
                "prompt_fragments": ["prompts/focus.md"],
                "tools": ["echo"],
            }
        ),
        encoding="utf-8",
    )

    registry = SkillRegistry.load(SkillLoader(tmp_path), ["focus"], context={"topic": "agents"})

    assert registry.names() == ["focus"]
    assert registry.prompt_text() == "Focus on agents."
    assert registry.tool_names() == ["echo"]
