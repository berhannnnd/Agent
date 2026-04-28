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
from agent.runtime import AgentResult
from agent.schema import Message, RuntimeEvent


class FakeRuntime:
    provider = "openai-chat"
    model = "test-model"


class FakeSession:
    def __init__(self):
        self.runtime = FakeRuntime()
        self.messages = []
        self.cleared = False

    async def stream(self, text, run_id=None):
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
        async def stream(self, text, run_id=None):
            raise RuntimeError("unexpected failure")
            yield

    monkeypatch.setattr(cli_module, "create_agent_session", lambda **kwargs: FailingSession())

    result = CliRunner().invoke(cli_module.client, ["chat"], input="hello\n/exit\n")

    assert result.exit_code == 0
    assert "error: unexpected failure" in result.stdout
    assert "Traceback" not in result.stdout


def test_cli_coding_profile_uses_current_workspace_and_tools(monkeypatch, tmp_path):
    session = FakeSession()
    captured = {}

    def fake_create_session(**kwargs):
        captured.update(kwargs)
        return session

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cli_module, "create_agent_session", fake_create_session)

    result = CliRunner().invoke(cli_module.client, ["chat"], input="/exit\n")

    assert result.exit_code == 0
    spec = captured["spec"]
    assert spec.workspace.path == str(tmp_path)
    assert "filesystem.write" in spec.enabled_tools
    assert "patch.apply" in spec.enabled_tools
    assert "shell.run" in spec.enabled_tools
    assert spec.tool_permissions.mode == "auto"
    assert "patch.apply" in spec.tool_permissions.approval_required_tools
    assert captured["checkpoint_store"] is not None


def test_cli_prompts_for_tool_approval_and_resumes(monkeypatch):
    class ApprovalSession(FakeSession):
        def __init__(self):
            super().__init__()
            self.resume_args = None

        async def stream(self, text, run_id=None):
            self.messages.append(text)
            yield RuntimeEvent(
                type="tool_approval_required",
                name="filesystem.write",
                payload={
                    "approval_id": "call-1",
                    "tool_call": {"id": "call-1", "name": "filesystem.write", "arguments": {"path": "game.html"}},
                    "impact": {"risk": "medium"},
                },
            )
            yield RuntimeEvent(type="done", name="assistant", payload={"status": "awaiting_approval", "content": "tool approval required"})

        async def resume(self, run_id, approvals=None, approval_scopes=None):
            self.resume_args = (approvals, approval_scopes)
            return AgentResult(
                content="created",
                messages=[Message.from_text("assistant", "created")],
                events=[
                    RuntimeEvent(type="tool_approval_decision", name="filesystem.write", payload={"approval_id": "call-1", "scope": "allow_for_run"}),
                    RuntimeEvent(type="model_message", name="assistant", payload={"content": "created"}),
                ],
            )

    session = ApprovalSession()
    monkeypatch.setattr(cli_module, "create_agent_session", lambda **kwargs: session)

    result = CliRunner().invoke(cli_module.client, ["chat"], input="make game\nr\n/exit\n")

    assert result.exit_code == 0
    assert "approval> filesystem.write risk=medium" in result.stdout
    assert "assistant> created" in result.stdout
    assert session.resume_args == ({"call-1": True}, {"call-1": "allow_for_run"})
