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

import pytest

from agent.schema import ToolCall
from agent.capabilities.skills import SkillLoader, SkillRegistry
from agent.capabilities.tools.mcp import MCPServerConfig, MCPToolDefinition, MCPToolProvider
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
    provider = MCPToolProvider(client=client, server=MCPServerConfig(name="docs"))

    asyncio.run(provider.load_tools(registry))
    result = asyncio.run(registry.execute("mcp_docs_search", {"query": "agents"}))

    assert registry.specs(["mcp_docs_search"])[0].name == "mcp_docs_search"
    assert json.loads(result.content)["answer"] == "agents"
    assert client.called == [("search", {"query": "agents"})]


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
