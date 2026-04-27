# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：test_agent_runtime.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

import asyncio

import pytest

from app.agent.runtime import AgentRuntime, AgentRuntimeError, AgentSession, ScriptedModelClient
from app.agent.schema import Message, ModelResponse, ModelStreamEvent, ToolCall
from app.agent.tools.registry import ToolRegistry


def test_agent_runtime_runs_model_tool_model_loop():
    llm = ScriptedModelClient(
        [
            ModelResponse(
                message=Message.from_text(
                    "assistant",
                    "",
                    tool_calls=[ToolCall(id="call-1", name="echo", arguments={"text": "hi"})],
                ),
                stop_reason="tool_calls",
            ),
            ModelResponse(message=Message.from_text("assistant", "final answer")),
        ]
    )
    tools = ToolRegistry()
    tools.register("echo", "Echo", {}, lambda text: text)
    runtime = AgentRuntime(model_client=llm, tools=tools, provider="scripted", model="scripted")

    result = asyncio.run(runtime.run([Message.from_text("user", "say hi")]))

    assert result.content == "final answer"
    assert result.tool_results[0].content == "hi"
    assert [message.role for message in result.messages] == ["user", "assistant", "tool", "assistant"]


def test_agent_session_commits_history_only_after_success():
    llm = ScriptedModelClient([])
    tools = ToolRegistry()
    runtime = AgentRuntime(model_client=llm, tools=tools, provider="scripted", model="scripted")
    session = AgentSession(runtime=runtime, system_prompt="Be concise.")

    with pytest.raises(RuntimeError):
        asyncio.run(session.send("hello"))

    assert [message.role for message in session.messages] == ["system"]


def test_agent_runtime_guard_stops_infinite_tool_loop():
    llm = ScriptedModelClient(
        [
            ModelResponse(
                message=Message.from_text(
                    "assistant",
                    "",
                    tool_calls=[ToolCall(id="call-1", name="echo", arguments={"text": "hi"})],
                )
            )
        ]
    )
    tools = ToolRegistry()
    tools.register("echo", "Echo", {}, lambda text: text)
    runtime = AgentRuntime(
        model_client=llm,
        tools=tools,
        provider="scripted",
        model="scripted",
        max_tool_iterations=1,
    )

    with pytest.raises(AgentRuntimeError):
        asyncio.run(runtime.run([Message.from_text("user", "loop")]))


def test_agent_runtime_streams_text_and_tool_events():
    llm = ScriptedModelClient(
        [
            [
                ModelStreamEvent(type="text_delta", delta="hel"),
                ModelStreamEvent(type="text_delta", delta="lo"),
                ModelStreamEvent(type="message", response=ModelResponse(message=Message.from_text("assistant", "hello"))),
            ]
        ]
    )
    runtime = AgentRuntime(model_client=llm, tools=ToolRegistry(), provider="scripted", model="scripted")

    async def collect():
        return [event async for event in runtime.stream([Message.from_text("user", "hi")])]

    events = asyncio.run(collect())

    assert [event.type for event in events] == ["text_delta", "text_delta", "done"]
    assert "".join(event.payload.get("delta", "") for event in events) == "hello"


def test_agent_session_stream_commits_completed_history():
    llm = ScriptedModelClient(
        [
            [
                ModelStreamEvent(type="text_delta", delta="hello"),
                ModelStreamEvent(type="message", response=ModelResponse(message=Message.from_text("assistant", "hello"))),
            ]
        ]
    )
    runtime = AgentRuntime(model_client=llm, tools=ToolRegistry(), provider="scripted", model="scripted")
    session = AgentSession(runtime=runtime, system_prompt="Be concise.")

    async def drain():
        return [event async for event in session.stream("hi")]

    asyncio.run(drain())

    assert [message.role for message in session.messages] == ["system", "user", "assistant"]
    assert session.messages[-1].content_text() == "hello"
