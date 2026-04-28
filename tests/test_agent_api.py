# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：test_agent_api.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

import asyncio

from fastapi.testclient import TestClient

from gateway.api.agent import api_agent
from gateway.api.agent.schemas import AgentChatRequest
from gateway.app import create_app
from agent.specs import AgentSpec
from agent.runtime import AgentResult, InMemoryCheckpointStore, RuntimeCheckpoint
from agent.schema import Message, RuntimeEvent, ToolCall
from agent.tasks import TaskStepRecord


class FakeSession:
    async def send(self, text, run_id=None, task_id=None):
        return AgentResult(
            content=f"ok: {text}",
            messages=[Message.from_text("user", text), Message.from_text("assistant", f"ok: {text}")],
            tool_results=[],
            events=[RuntimeEvent(type="model_message", name="assistant", payload={"content": f"ok: {text}"})],
        )

    async def stream(self, text, run_id=None, task_id=None):
        yield RuntimeEvent(type="text_delta", name="assistant", payload={"delta": "ok"})
        yield RuntimeEvent(type="done", name="assistant", payload={"content": f"ok: {text}"})


class FakeApprovalSession:
    async def resume(self, run_id, approvals=None, task_id=None):
        assert approvals == {"call-1": True}
        return AgentResult(
            content="resumed",
            messages=[Message.from_text("assistant", "resumed")],
            events=[
                RuntimeEvent(type="tool_approval_required", name="echo", payload={"approval_id": "call-1"}),
                RuntimeEvent(type="tool_approval_decision", name="echo", payload={"approval_id": "call-1", "approved": True}),
                RuntimeEvent(type="model_message", name="assistant", payload={"content": "resumed"}),
            ],
        )


def test_agent_chat_api_returns_final_answer(monkeypatch):
    async def create_session(**kwargs):
        return FakeSession()

    monkeypatch.setattr(api_agent, "create_agent_session", create_session)
    client = TestClient(create_app())

    response = client.post("/api/v1/agent/chat", json={"message": "hello"})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["run_id"].startswith("run_")
    assert data["content"] == "ok: hello"


def test_agent_chat_request_builds_agent_spec():
    spec = AgentChatRequest(
        message="hello",
        provider="openai-chat",
        model="gpt-test",
        user_id="user 1",
        agent_id="agent 1",
        enabled_tools=["echo"],
    ).to_agent_spec()

    assert spec.model.provider == "openai-chat"
    assert spec.model.model == "gpt-test"
    assert spec.workspace.user_id == "user 1"
    assert spec.workspace.agent_id == "agent 1"
    assert spec.enabled_tools == ["echo"]


def test_agent_chat_request_builds_tool_permission_spec():
    spec = AgentChatRequest(
        message="hello",
        permission_profile="ask",
        approval_required_tools=["shell"],
        denied_tools=["delete"],
    ).to_agent_spec()

    assert spec.tool_permissions.mode == "ask"
    assert spec.tool_permissions.approval_required_tools == ["shell"]
    assert spec.tool_permissions.denied_tools == ["delete"]


def test_agent_stream_api_returns_sse_events(monkeypatch):
    async def create_session(**kwargs):
        return FakeSession()

    monkeypatch.setattr(api_agent, "create_agent_session", create_session)
    client = TestClient(create_app())

    response = client.post("/api/v1/agent/chat/stream", json={"message": "hello"})

    assert response.status_code == 200
    assert "event: run_created" in response.text
    assert "event: text_delta" in response.text
    assert "event: done" in response.text


def test_agent_run_api_returns_record(monkeypatch):
    async def create_session(**kwargs):
        return FakeSession()

    monkeypatch.setattr(api_agent, "create_agent_session", create_session)
    client = TestClient(create_app())

    chat_response = client.post("/api/v1/agent/chat", json={"message": "hello"})
    run_id = chat_response.json()["data"]["run_id"]
    run_response = client.get(f"/api/v1/agent/runs/{run_id}")

    assert run_response.status_code == 200
    data = run_response.json()["data"]
    assert data["run_id"] == run_id
    assert data["status"] == "finished"
    assert [event["type"] for event in data["events"]] == ["run_created", "model_message"]


def test_agent_run_trace_api_returns_spans(monkeypatch):
    async def create_session(**kwargs):
        return FakeSession()

    monkeypatch.setattr(api_agent, "create_agent_session", create_session)
    client = TestClient(create_app())

    chat_response = client.post("/api/v1/agent/chat", json={"message": "hello"})
    run_id = chat_response.json()["data"]["run_id"]
    trace_response = client.get(f"/api/v1/agent/runs/{run_id}/trace")

    assert trace_response.status_code == 200
    data = trace_response.json()["data"]
    assert data["run_id"] == run_id
    assert [span["kind"] for span in data["spans"]] == ["run", "model"]
    assert data["spans"][0]["status"] == "done"
    assert data["approvals"] == []
    assert data["sandbox_leases"] == []
    assert data["sandbox_artifacts"]["downloads"] == "artifacts/downloads"
    assert data["sandbox_events"] == []
    assert data["sandbox_snapshots"] == []


def test_agent_run_api_returns_404_for_unknown_run():
    client = TestClient(create_app())

    response = client.get("/api/v1/agent/runs/missing")

    assert response.status_code == 404


def test_agent_task_api_creates_reads_and_runs_task(monkeypatch):
    async def create_session(**kwargs):
        return FakeSession()

    monkeypatch.setattr(api_agent, "create_agent_session", create_session)
    client = TestClient(create_app())

    create_response = client.post(
        "/api/v1/agent/tasks",
        json={
            "message": "complete the foundation",
            "title": "Foundation task",
            "tenant_id": "tenant-1",
            "user_id": "user-1",
            "agent_id": "agent-1",
        },
    )
    task = create_response.json()["data"]
    run_response = client.post(f"/api/v1/agent/tasks/{task['task_id']}/run")
    get_response = client.get(f"/api/v1/agent/tasks/{task['task_id']}")

    assert create_response.status_code == 200
    assert task["title"] == "Foundation task"
    assert run_response.status_code == 200
    assert run_response.json()["data"]["task"]["status"] == "finished"
    assert run_response.json()["data"]["step"]["status"] == "succeeded"
    assert get_response.json()["data"]["steps"][0]["output"] == "ok: complete the foundation"


def test_agent_task_api_returns_404_for_unknown_task():
    client = TestClient(create_app())

    response = client.post("/api/v1/agent/tasks/missing/run")

    assert response.status_code == 404


def test_agent_run_approval_api_resumes_checkpoint(monkeypatch):
    async def create_session(**kwargs):
        return FakeApprovalSession()

    async def seed():
        call = ToolCall(id="call-1", name="echo", arguments={"text": "hi"})
        store = InMemoryCheckpointStore()
        await store.save(
            RuntimeCheckpoint(
                run_id="run-approval",
                step="approval_required",
                iteration=0,
                messages=[Message.from_text("assistant", "", tool_calls=[call])],
                events=[RuntimeEvent(type="tool_approval_required", name="echo", payload={"approval_id": "call-1"})],
                pending_tool_calls=[call],
            )
        )
        record = await api_agent.run_service.store.create_run(AgentSpec.from_overrides(agent_id="agent-1"), run_id="run-approval")
        await api_agent.run_service.record_event(record.run_id, RuntimeEvent(type="tool_approval_required", name="echo", payload={"approval_id": "call-1"}))
        await api_agent.run_service.pause_for_approval(record.run_id)
        task = await api_agent.persistence.tasks.create_task(record.to_agent_spec(), title="Approval task", input="approve")
        await api_agent.persistence.tasks.add_step(
            TaskStepRecord.create(task_id=task.task_id, index=0, name="execute", run_id=record.run_id)
        )
        return store

    monkeypatch.setattr(api_agent, "checkpoint_store", asyncio.run(seed()))
    monkeypatch.setattr(api_agent, "create_agent_session", create_session)
    client = TestClient(create_app())

    response = client.post("/api/v1/agent/runs/run-approval/approval", json={"tool_call_ids": ["call-1"], "approved": True})

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["status"] == "finished"
    assert [event["type"] for event in data["events"]] == ["tool_approval_decision", "model_message"]
    step = asyncio.run(api_agent.persistence.tasks.load_step_for_run("run-approval"))
    task = asyncio.run(api_agent.persistence.tasks.load_task(step.task_id))
    assert step.status.value == "succeeded"
    assert task.status.value == "finished"
