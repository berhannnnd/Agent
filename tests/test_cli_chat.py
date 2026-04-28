# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：test_cli_chat.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

import asyncio
from types import SimpleNamespace

from typer.testing import CliRunner

from agent.config import ModelProfile, build_model_profiles, resolve_model_profile
from agent.config import profiles as model_profile_module
from agent.runtime import AgentResult
from agent.schema import Message, RuntimeEvent
from cli import main as cli_module
from cli.commands import COMMANDS
from cli.ui import RuntimeEventAdapter, SlashCommandCompleter, ToolActivity, TurnActivity


class FakeRuntime:
    protocol = "openai-chat"
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
    assert "Agents Code" in result.stdout
    assert "openai-chat · test-model" in result.stdout
    assert "ok: hello" in result.stdout
    assert "assistant>" not in result.stdout
    assert session.messages == ["hello"]


def test_cli_chat_clear_command_resets_session(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(cli_module, "create_agent_session", lambda **kwargs: session)

    result = CliRunner().invoke(cli_module.client, ["chat"], input="/clear\n/quit\n")

    assert result.exit_code == 0
    assert "cleared" in result.stdout
    assert session.cleared is True


def test_cli_chat_help_and_status_commands(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(cli_module, "create_agent_session", lambda **kwargs: session)

    result = CliRunner().invoke(cli_module.client, ["chat"], input="/help\n/status\n/doctor\n/tools\n/quit\n")

    assert result.exit_code == 0
    assert "commands" in result.stdout
    assert "/workspace" in result.stdout
    assert "status" in result.stdout
    assert "doctor" in result.stdout
    assert "enabled tools" in result.stdout


def test_slash_command_completer_shows_command_menu():
    from prompt_toolkit.document import Document

    completions = list(SlashCommandCompleter(COMMANDS).get_completions(Document("/st"), None))

    assert [completion.text for completion in completions] == ["/status"]
    assert "protocol" in str(completions[0].display_meta)

    profiles = [
        ModelProfile(
            name="openai-chat",
            protocol="openai-chat",
            model="gpt-test",
            base_url="https://api.openai.com/v1",
            api_key="key",
        ),
        ModelProfile(
            name="openai-responses",
            protocol="openai-responses",
            model="gpt-test",
            base_url="https://api.openai.com/v1",
            api_key="key",
        ),
    ]
    model_completions = list(SlashCommandCompleter(COMMANDS, profiles).get_completions(Document("/model openai"), None))
    assert [completion.text for completion in model_completions] == ["openai-chat", "openai-responses"]


def test_runtime_events_adapt_to_cli_ui_events():
    adapter = RuntimeEventAdapter()

    event = RuntimeEvent(
        type="tool_start",
        name="filesystem.read",
        payload={"id": "call-1", "arguments": {"path": "README.md"}, "impact": {"risk": "low"}},
    )

    ui_event = adapter.adapt(event)

    assert ui_event is not None
    assert ui_event.type == "tool_started"
    assert ui_event.name == "filesystem.read"
    assert ui_event.payload["id"] == "call-1"
    assert ui_event.payload["arguments"] == {"path": "README.md"}
    assert ui_event.payload["risk"] == "low"


def test_turn_activity_tracks_tool_state_and_summary():
    activity = TurnActivity()
    activity.record_tool_start(
        ToolActivity(
            id="call-1",
            name="filesystem.read",
            arguments={"path": "README.md"},
            risk="low",
        )
    )

    summary = activity.record_tool_result("filesystem.read", '{"path":"README.md","content":"hello"}', tool_id="call-1")

    assert summary == "Read 1 file"
    assert activity.tool_count == 1
    assert activity.tools["call-1"].status == "finished"
    assert activity.tools["call-1"].summary == "Read 1 file"


def test_model_profiles_include_custom_env_profiles(monkeypatch, tmp_path):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "AGENT_MODEL_PROFILES=kimi",
                "AGENT_MODEL_PROFILE_KIMI_PROTOCOL=openai-chat",
                "AGENT_MODEL_PROFILE_KIMI_BASE_URL=https://api.moonshot.cn/v1",
                "AGENT_MODEL_PROFILE_KIMI_MODEL=kimi-k2",
                "AGENT_MODEL_PROFILE_KIMI_API_KEY=secret",
                "AGENT_MODEL_PROFILE_KIMI_ALIASES=moonshot",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(model_profile_module, "ENV_FILE", str(env_file))
    settings = SimpleNamespace(
        agent=SimpleNamespace(CLAUDE_MODEL="", CLAUDE_BASE_URL="", CLAUDE_API_KEY=""),
        models=SimpleNamespace(
            openai=SimpleNamespace(MODEL="", BASE_URL="", API_KEY=""),
            openai_responses=SimpleNamespace(MODEL="", BASE_URL="", API_KEY=""),
            anthropic=SimpleNamespace(MODEL="", BASE_URL="", API_KEY=""),
            gemini=SimpleNamespace(MODEL="", BASE_URL="", API_KEY=""),
        ),
    )

    profile = resolve_model_profile(build_model_profiles(settings), "kimi")

    assert profile is not None
    assert profile.name == "kimi"
    assert profile.protocol == "openai-chat"
    assert profile.model == "kimi-k2"
    assert profile.base_url == "https://api.moonshot.cn/v1"
    assert profile.api_key == "secret"
    assert profile.matches("moonshot")


def test_cli_chat_reports_turn_errors_without_traceback(monkeypatch):
    class FailingSession(FakeSession):
        async def stream(self, text, run_id=None):
            raise RuntimeError("unexpected failure")
            yield

    monkeypatch.setattr(cli_module, "create_agent_session", lambda **kwargs: FailingSession())

    result = CliRunner().invoke(cli_module.client, ["chat"], input="hello\n/exit\n")

    assert result.exit_code == 0
    assert "error" in result.stdout
    assert "unexpected failure" in result.stdout
    assert "Traceback" not in result.stdout


def test_cli_collapses_tool_results_before_answer(monkeypatch):
    class ToolSession(FakeSession):
        async def stream(self, text, run_id=None):
            self.messages.append(text)
            yield RuntimeEvent(type="tool_start", name="filesystem.list", payload={"arguments": {"path": "."}})
            yield RuntimeEvent(
                type="tool_result",
                name="filesystem.list",
                payload={
                    "content": '{"path": ".", "entries": [{"name": "README.md", "path": "README.md", "type": "file"}]}',
                    "is_error": False,
                },
            )
            yield RuntimeEvent(type="text_delta", name="assistant", payload={"delta": "done"})
            yield RuntimeEvent(type="done", name="assistant", payload={"content": "done"})

    monkeypatch.setattr(cli_module, "create_agent_session", lambda **kwargs: ToolSession())

    result = CliRunner().invoke(cli_module.client, ["chat"], input="inspect\n/exit\n")

    assert result.exit_code == 0
    assert "Listed 1 directory" in result.stdout
    assert "filesystem.list" in result.stdout
    assert "tool result>" not in result.stdout
    assert '"entries"' not in result.stdout


def test_cli_shows_thinking_tool_details_and_done_state(monkeypatch):
    class DetailSession(FakeSession):
        async def stream(self, text, run_id=None):
            yield RuntimeEvent(type="reasoning_delta", name="assistant", payload={"delta": "think"})
            yield RuntimeEvent(type="tool_start", name="filesystem.read", payload={"arguments": {"path": "README.md"}})
            yield RuntimeEvent(
                type="tool_result",
                name="filesystem.read",
                payload={"content": '{"path":"README.md","content":"hello"}', "is_error": False},
            )
            yield RuntimeEvent(type="text_delta", name="assistant", payload={"delta": "done"})
            yield RuntimeEvent(type="done", name="assistant", payload={"content": "done", "status": "finished"})

    monkeypatch.setattr(cli_module, "create_agent_session", lambda **kwargs: DetailSession())

    result = CliRunner().invoke(cli_module.client, ["chat"], input="inspect\n/exit\n")

    assert result.exit_code == 0
    assert "thinking" in result.stdout
    assert "openai-chat · test-model" in result.stdout
    assert "reasoning" in result.stdout
    assert "filesystem.read" in result.stdout
    assert "README.md" in result.stdout
    assert "Read 1 file" in result.stdout
    assert "done" in result.stdout


def test_cli_shows_model_retry_and_does_not_repeat_error_as_assistant(monkeypatch):
    class RetrySession(FakeSession):
        async def stream(self, text, run_id=None):
            yield RuntimeEvent(
                type="model_retry",
                name="model",
                payload={
                    "next_attempt": 2,
                    "max_attempts": 3,
                    "delay_seconds": 0,
                    "error": "connect failed",
                },
            )
            yield RuntimeEvent(type="error", name="model", payload={"message": "model error: connect failed"})
            yield RuntimeEvent(
                type="done",
                name="assistant",
                payload={"content": "model error: connect failed", "status": "error"},
            )

    monkeypatch.setattr(cli_module, "create_agent_session", lambda **kwargs: RetrySession())

    result = CliRunner().invoke(cli_module.client, ["chat"], input="hello\n/exit\n")

    assert result.exit_code == 0
    assert "retry" in result.stdout
    assert "2/3" in result.stdout
    assert "model error: connect failed" in result.stdout
    assert result.stdout.count("model error: connect failed") == 1


def test_cli_reuses_one_event_loop_for_multiple_turns(monkeypatch):
    class LoopSession(FakeSession):
        def __init__(self):
            super().__init__()
            self.loop_ids = []

        async def stream(self, text, run_id=None):
            self.loop_ids.append(id(asyncio.get_running_loop()))
            yield RuntimeEvent(type="text_delta", name="assistant", payload={"delta": text})
            yield RuntimeEvent(type="done", name="assistant", payload={"content": text, "status": "finished"})

    session = LoopSession()
    monkeypatch.setattr(cli_module, "create_agent_session", lambda **kwargs: session)

    result = CliRunner().invoke(cli_module.client, ["chat"], input="one\ntwo\n/exit\n")

    assert result.exit_code == 0
    assert len(session.loop_ids) == 2
    assert len(set(session.loop_ids)) == 1


def test_cli_model_command_switches_session(monkeypatch):
    class Runtime:
        def __init__(self, protocol, model):
            self.protocol = protocol
            self.model = model

    class SwitchSession(FakeSession):
        def __init__(self, protocol, model):
            super().__init__()
            self.runtime = Runtime(protocol, model)
            self.messages = [Message.from_text("system", "system prompt")]

    sessions = []

    def fake_create_session(**kwargs):
        spec = kwargs["spec"]
        protocol = spec.model.protocol or "openai-chat"
        model = spec.model.model or "initial-model"
        session = SwitchSession(protocol, model)
        sessions.append(session)
        return session

    monkeypatch.setattr(cli_module, "create_agent_session", fake_create_session)
    monkeypatch.setattr(
        cli_module,
        "build_model_profiles",
        lambda settings: [
            ModelProfile(
                name="coding-model",
                protocol="openai-chat",
                model="next-model",
                base_url="https://api.example/v1",
                api_key="key",
            )
        ],
    )

    result = CliRunner().invoke(cli_module.client, ["chat"], input="/model coding-model\n/exit\n")

    assert result.exit_code == 0
    assert len(sessions) == 2
    assert sessions[1].runtime.protocol == "openai-chat"
    assert sessions[1].runtime.model == "next-model"
    assert sessions[1].messages == sessions[0].messages
    assert "switched to openai-chat · next-model" in result.stdout
    assert "profile coding-model" in result.stdout


def test_cli_chat_starts_with_model_profile(monkeypatch):
    sessions = []

    def fake_create_session(**kwargs):
        spec = kwargs["spec"]
        session = FakeSession()
        session.runtime = type("Runtime", (), {"protocol": spec.model.protocol, "model": spec.model.model})()
        sessions.append(session)
        return session

    monkeypatch.setattr(cli_module, "create_agent_session", fake_create_session)
    monkeypatch.setattr(
        cli_module,
        "build_model_profiles",
        lambda settings: [
            ModelProfile(
                name="kimi",
                protocol="openai-chat",
                model="kimi-k2",
                base_url="https://api.moonshot.cn/v1",
                api_key="key",
            )
        ],
    )

    result = CliRunner().invoke(cli_module.client, ["chat", "--model-profile", "kimi"], input="/exit\n")

    assert result.exit_code == 0
    assert sessions[0].runtime.protocol == "openai-chat"
    assert sessions[0].runtime.model == "kimi-k2"


def test_cli_model_command_rejects_unknown_single_name(monkeypatch):
    session = FakeSession()
    monkeypatch.setattr(cli_module, "create_agent_session", lambda **kwargs: session)

    result = CliRunner().invoke(cli_module.client, ["chat"], input="/model not-a-profile\n/exit\n")

    assert result.exit_code == 0
    assert "unknown model profile: not-a-profile" in result.stdout


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
    assert "approval" in result.stdout
    assert "filesystem.write · risk medium" in result.stdout
    assert "created" in result.stdout
    assert session.resume_args == ({"call-1": True}, {"call-1": "allow_for_run"})
