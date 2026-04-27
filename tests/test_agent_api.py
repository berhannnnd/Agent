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

from app.api.agent import api_agent
from app.app import create_app
from app.agent.runtime import AgentResult
from app.agent.schema import Message, RuntimeEvent


class FakeSession:
    async def send(self, text):
        return AgentResult(
            content=f"ok: {text}",
            messages=[Message.from_text("user", text), Message.from_text("assistant", f"ok: {text}")],
            tool_results=[],
            events=[RuntimeEvent(type="model_message", name="assistant", payload={"content": f"ok: {text}"})],
        )

    async def stream(self, text):
        yield RuntimeEvent(type="text_delta", name="assistant", payload={"delta": "ok"})
        yield RuntimeEvent(type="done", name="assistant", payload={"content": f"ok: {text}"})


def test_agent_chat_api_returns_final_answer(monkeypatch):
    monkeypatch.setattr(api_agent, "create_agent_session", lambda **kwargs: FakeSession())
    client = TestClient(create_app())

    response = client.post("/api/v1/agent/chat", json={"message": "hello"})

    assert response.status_code == 200
    assert response.json()["data"]["content"] == "ok: hello"


def test_agent_stream_api_returns_sse_events(monkeypatch):
    monkeypatch.setattr(api_agent, "create_agent_session", lambda **kwargs: FakeSession())
    client = TestClient(create_app())

    response = client.post("/api/v1/agent/chat/stream", json={"message": "hello"})

    assert response.status_code == 200
    assert "event: text_delta" in response.text
    assert "event: done" in response.text
