# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：test_cli_chat.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from typer.testing import CliRunner

from cli import main as cli_module
from agent.schema import RuntimeEvent


class FakeRuntime:
    provider = "openai-chat"
    model = "test-model"


class FakeSession:
    def __init__(self):
        self.runtime = FakeRuntime()
        self.messages = []
        self.cleared = False

    async def stream(self, text):
        self.messages.append(text)
        yield RuntimeEvent(type="text_delta", name="assistant", payload={"delta": "ok: "})
        yield RuntimeEvent(type="text_delta", name="assistant", payload={"delta": text})
        yield RuntimeEvent(type="done", name="assistant", payload={"content": f"ok: {text}"})

    def clear(self):
        self.cleared = True


def test_cli_chat_streams_until_exit(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(cli_module, "create_agent_session", lambda **kwargs: session)

    result = CliRunner().invoke(cli_module.client, ["chat"], input="hello\n/exit\n")

    assert result.exit_code == 0
    assert "agent provider: openai-chat/test-model" in result.stdout
    assert "assistant> ok: hello" in result.stdout
    assert session.messages == ["hello"]


def test_cli_chat_clear_command_resets_session(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(cli_module, "create_agent_session", lambda **kwargs: session)

    result = CliRunner().invoke(cli_module.client, ["chat"], input="/clear\n/quit\n")

    assert result.exit_code == 0
    assert "cleared" in result.stdout
    assert session.cleared is True


def test_cli_chat_reports_turn_errors_without_traceback(monkeypatch):
    class FailingSession(FakeSession):
        async def stream(self, text):
            raise RuntimeError("unexpected failure")
            yield

    monkeypatch.setattr(cli_module, "create_agent_session", lambda **kwargs: FailingSession())

    result = CliRunner().invoke(cli_module.client, ["chat"], input="hello\n/exit\n")

    assert result.exit_code == 0
    assert "error: unexpected failure" in result.stdout
    assert "Traceback" not in result.stdout
