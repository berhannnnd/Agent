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

from agent.runtime import (
    AgentRuntime,
    AgentSession,
    InMemoryCheckpointStore,
    RuntimeCheckpoint,
    ScriptedModelClient,
    StaticToolPermissionPolicy,
)
from agent.schema import Message, ModelResponse, ModelStreamEvent, ToolCall
from agent.tools.registry import ToolRegistry


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


def test_agent_runtime_denies_tools_through_permission_policy():
    llm = ScriptedModelClient(
        [
            ModelResponse(
                message=Message.from_text(
                    "assistant",
                    "",
                    tool_calls=[ToolCall(id="call-1", name="dangerous", arguments={})],
                )
            ),
            ModelResponse(message=Message.from_text("assistant", "handled denial")),
        ]
    )
    tools = ToolRegistry()
    tools.register("dangerous", "Dangerous", {}, lambda: "should not run")
    runtime = AgentRuntime(
        model_client=llm,
        tools=tools,
        provider="scripted",
        model="scripted",
        permission_policy=StaticToolPermissionPolicy(denied_tools={"dangerous"}),
    )

    result = asyncio.run(runtime.run([Message.from_text("user", "run it")]))

    assert result.content == "handled denial"
    assert result.tool_results[0].is_error is True
    assert "denied" in result.tool_results[0].content
    assert result.messages[2].role == "tool"


def test_agent_runtime_pauses_when_tool_requires_approval():
    call = ToolCall(id="call-1", name="dangerous", arguments={})
    llm = ScriptedModelClient([ModelResponse(message=Message.from_text("assistant", "", tool_calls=[call]))])
    store = InMemoryCheckpointStore()
    tools = ToolRegistry()
    ran = {"value": False}
    tools.register("dangerous", "Dangerous", {}, lambda: ran.update(value=True))
    runtime = AgentRuntime(
        model_client=llm,
        tools=tools,
        provider="scripted",
        model="scripted",
        permission_policy=StaticToolPermissionPolicy(approval_required_tools={"dangerous"}),
        checkpoint_store=store,
    )

    async def execute():
        result = await runtime.run([Message.from_text("user", "run it")], run_id="run-1")
        checkpoint = await store.load("run-1")
        return result, checkpoint

    result, checkpoint = asyncio.run(execute())

    assert result.status == "awaiting_approval"
    assert result.content == "tool approval required"
    assert ran["value"] is False
    assert checkpoint is not None
    assert checkpoint.step == "approval_required"
    assert checkpoint.pending_tool_calls == [call]
    assert any(event.type == "tool_approval_required" for event in result.events)


def test_agent_runtime_resumes_after_tool_approval():
    call = ToolCall(id="call-1", name="echo", arguments={"text": "hi"})
    llm = ScriptedModelClient(
        [
            ModelResponse(message=Message.from_text("assistant", "", tool_calls=[call])),
            ModelResponse(message=Message.from_text("assistant", "approved")),
        ]
    )
    store = InMemoryCheckpointStore()
    tools = ToolRegistry()
    tools.register("echo", "Echo", {}, lambda text: text)
    runtime = AgentRuntime(
        model_client=llm,
        tools=tools,
        provider="scripted",
        model="scripted",
        permission_policy=StaticToolPermissionPolicy(approval_required_tools={"echo"}),
        checkpoint_store=store,
    )

    async def execute():
        paused = await runtime.run([Message.from_text("user", "say hi")], run_id="run-1")
        resumed = await runtime.resume("run-1", approvals={"call-1": True})
        return paused, resumed

    paused, resumed = asyncio.run(execute())

    assert paused.status == "awaiting_approval"
    assert resumed.status == "finished"
    assert resumed.content == "approved"
    assert resumed.tool_results[0].content == "hi"
    assert [event.type for event in resumed.events if event.type.startswith("tool_approval")] == [
        "tool_approval_required",
        "tool_approval_decision",
    ]


def test_agent_runtime_saves_finished_checkpoint():
    llm = ScriptedModelClient([ModelResponse(message=Message.from_text("assistant", "done"))])
    store = InMemoryCheckpointStore()
    runtime = AgentRuntime(
        model_client=llm,
        tools=ToolRegistry(),
        provider="scripted",
        model="scripted",
        checkpoint_store=store,
    )

    async def execute():
        result = await runtime.run([Message.from_text("user", "hi")], run_id="run-1")
        checkpoint = await store.load("run-1")
        return result, checkpoint

    result, checkpoint = asyncio.run(execute())

    assert result.content == "done"
    assert checkpoint is not None
    assert checkpoint.step == "finished"
    assert [message.role for message in checkpoint.messages] == ["user", "assistant"]


def test_agent_session_forwards_run_id_to_runtime_checkpoints():
    llm = ScriptedModelClient([ModelResponse(message=Message.from_text("assistant", "done"))])
    store = InMemoryCheckpointStore()
    runtime = AgentRuntime(
        model_client=llm,
        tools=ToolRegistry(),
        provider="scripted",
        model="scripted",
        checkpoint_store=store,
    )
    session = AgentSession(runtime=runtime)

    async def execute():
        await session.send("hi", run_id="run-1")
        return await store.load("run-1")

    checkpoint = asyncio.run(execute())

    assert checkpoint is not None
    assert checkpoint.step == "finished"


def test_agent_runtime_resumes_pending_tool_checkpoint():
    call = ToolCall(id="call-1", name="echo", arguments={"text": "hi"})
    checkpoint = RuntimeCheckpoint(
        run_id="run-1",
        step="model_response",
        iteration=0,
        messages=[
            Message.from_text("user", "say hi"),
            Message.from_text("assistant", "", tool_calls=[call]),
        ],
        pending_tool_calls=[call],
    )
    store = InMemoryCheckpointStore()

    async def seed_checkpoint():
        await store.save(checkpoint)

    asyncio.run(seed_checkpoint())
    llm = ScriptedModelClient([ModelResponse(message=Message.from_text("assistant", "resumed"))])
    tools = ToolRegistry()
    tools.register("echo", "Echo", {}, lambda text: text)
    runtime = AgentRuntime(
        model_client=llm,
        tools=tools,
        provider="scripted",
        model="scripted",
        checkpoint_store=store,
    )

    result = asyncio.run(runtime.resume("run-1"))

    assert result.content == "resumed"
    assert result.tool_results[0].content == "hi"
    assert [message.role for message in result.messages] == ["user", "assistant", "tool", "assistant"]


def test_agent_session_commits_history_on_error():
    llm = ScriptedModelClient([])
    tools = ToolRegistry()
    runtime = AgentRuntime(model_client=llm, tools=tools, provider="scripted", model="scripted")
    session = AgentSession(runtime=runtime, system_prompt="Be concise.")

    result = asyncio.run(session.send("hello"))

    assert result.content.startswith("unexpected error")
    assert [message.role for message in session.messages] == ["system", "user"]


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

    result = asyncio.run(runtime.run([Message.from_text("user", "loop")]))

    assert "exceeded max iterations" in result.content
    assert any(event.type == "error" for event in result.events)


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


def test_agent_runtime_streams_reasoning_events():
    llm = ScriptedModelClient(
        [
            [
                ModelStreamEvent(type="reasoning_delta", delta="think"),
                ModelStreamEvent(type="message", response=ModelResponse(message=Message.from_text("assistant", "done"))),
            ]
        ]
    )
    runtime = AgentRuntime(model_client=llm, tools=ToolRegistry(), provider="scripted", model="scripted")

    async def collect():
        return [event async for event in runtime.stream([Message.from_text("user", "hi")])]

    events = asyncio.run(collect())

    assert [event.type for event in events] == ["reasoning_delta", "done"]
    assert events[0].payload["delta"] == "think"


def test_agent_runtime_stream_done_uses_error_content_on_failure():
    llm = ScriptedModelClient([])
    runtime = AgentRuntime(model_client=llm, tools=ToolRegistry(), provider="scripted", model="scripted")

    async def collect():
        return [event async for event in runtime.stream([Message.from_text("user", "hi")])]

    events = asyncio.run(collect())

    assert events[-2].type == "error"
    assert events[-1].type == "done"
    assert events[-1].payload["content"].startswith("unexpected error")
    assert events[-1].payload["error"].startswith("unexpected error")


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
