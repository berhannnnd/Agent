# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：test_agent_api.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from fastapi.testclient import TestClient

from gateway.api.agent import api_agent
from gateway.api.agent.schemas import AgentChatRequest
from gateway.app import create_app
from agent.runtime import AgentResult
from agent.schema import Message, RuntimeEvent


class FakeSession:
    async def send(self, text, run_id=None):
        return AgentResult(
            content=f"ok: {text}",
            messages=[Message.from_text("user", text), Message.from_text("assistant", f"ok: {text}")],
            tool_results=[],
            events=[RuntimeEvent(type="model_message", name="assistant", payload={"content": f"ok: {text}"})],
        )

    async def stream(self, text, run_id=None):
        yield RuntimeEvent(type="text_delta", name="assistant", payload={"delta": "ok"})
        yield RuntimeEvent(type="done", name="assistant", payload={"content": f"ok: {text}"})


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
