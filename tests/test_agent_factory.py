# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：test_agent_factory.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

import asyncio
import json

import pytest

from agent.factory import AgentConfigError, AgentSpec, create_agent_session, resolve_model_client_config


class FakeModelConfig:
    API_KEY = ""
    BASE_URL = ""
    MODEL = ""


class FakeModelsConfig:
    def __init__(self):
        self.openai = FakeModelConfig()
        self.openai_responses = FakeModelConfig()
        self.anthropic = FakeModelConfig()
        self.gemini = FakeModelConfig()


class FakeAgentConfig:
    PROVIDER = "openai-chat"
    TIMEOUT = 60.0
    MAX_TOKENS = 4096
    MAX_TOOL_ITERATIONS = 8
    SYSTEM_PROMPT = ""
    ENABLED_TOOLS = ""
    SKILLS = ""
    WORKSPACE_ROOT = ".agents/workspaces"
    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1.0
    MAX_CONTEXT_TOKENS = 256000
    MAX_CONCURRENT_TOOLS = 10
    MAX_CONCURRENT_REQUESTS = 20
    TOOL_TIMEOUT = 60.0
    GUIDED_TOOLS = ""
    HTTP_PROXY = ""
    HTTPS_PROXY = ""
    ALL_PROXY = ""
    CLAUDE_API_KEY = ""
    CLAUDE_BASE_URL = ""
    CLAUDE_MODEL = ""


class FakeSettings:
    def __init__(self):
        self.agent = FakeAgentConfig()
        self.models = FakeModelsConfig()
        self.server = FakeServerConfig()
        self.mcp = FakeMcpConfig()


class FakeServerConfig:
    ROOT_PATH = "."


class FakeMcpConfig:
    SERVER_COMMAND = ""
    SERVER_NAME = ""
    CLIENT_TIMEOUT = 5.0


class FakeRuntimeClient:
    async def async_complete(self, request_data):
        raise RuntimeError("not used")

    async def async_stream(self, request_data):
        raise RuntimeError("not used")


def test_claude_config_prefers_agent_specific_values():
    settings = FakeSettings()
    settings.agent.CLAUDE_API_KEY = "project-key"
    settings.agent.CLAUDE_BASE_URL = "https://project.example/v1"
    settings.agent.CLAUDE_MODEL = "project-claude"
    settings.models.anthropic.API_KEY = "global-key"
    settings.models.anthropic.BASE_URL = "https://global.example/v1"
    settings.models.anthropic.MODEL = "global-claude"

    config = resolve_model_client_config(settings, provider="claude-messages")

    assert config.api_key == "project-key"
    assert config.base_url == "https://project.example/v1"
    assert config.model == "project-claude"


def test_claude_config_falls_back_to_anthropic_when_agent_specific_values_are_empty():
    settings = FakeSettings()
    settings.models.anthropic.API_KEY = "global-key"
    settings.models.anthropic.BASE_URL = "https://global.example/v1"
    settings.models.anthropic.MODEL = "global-claude"

    config = resolve_model_client_config(settings, provider="claude-messages")

    assert config.api_key == "global-key"
    assert config.base_url == "https://global.example/v1"
    assert config.model == "global-claude"


def test_partial_agent_claude_config_falls_back_to_global_anthropic_values():
    settings = FakeSettings()
    settings.agent.CLAUDE_BASE_URL = "https://project.example/v1"
    settings.agent.CLAUDE_MODEL = "project-claude"
    settings.models.anthropic.API_KEY = "global-key"

    config = resolve_model_client_config(settings, provider="claude-messages")

    assert config.api_key == "global-key"
    assert config.base_url == "https://project.example/v1"
    assert config.model == "project-claude"


def test_model_config_uses_project_proxy_settings():
    settings = FakeSettings()
    settings.models.openai.API_KEY = "key"
    settings.models.openai.MODEL = "model"
    settings.agent.HTTP_PROXY = "http://127.0.0.1:7890"
    settings.agent.HTTPS_PROXY = "http://127.0.0.1:7890"
    settings.agent.ALL_PROXY = "socks5://127.0.0.1:7890"

    config = resolve_model_client_config(settings, provider="openai-chat")

    assert config.proxy_url == "http://127.0.0.1:7890"


def test_create_session_composes_skill_prompt_and_declared_tools(tmp_path, monkeypatch):
    (tmp_path / "skills").mkdir()
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "focus.md").write_text("Focus on agents.", encoding="utf-8")
    (tmp_path / "skills" / "focus.json").write_text(
        json.dumps(
            {
                "name": "focus",
                "prompt_fragments": ["prompts/focus.md"],
                "tools": ["skill_tool"],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr("agent.assembly.session.ModelClient", lambda config: FakeRuntimeClient())
    settings = FakeSettings()
    settings.server.ROOT_PATH = tmp_path
    settings.agent.SYSTEM_PROMPT = "Base prompt."
    settings.agent.SKILLS = "focus"
    settings.agent.ENABLED_TOOLS = "base_tool"
    settings.models.openai.API_KEY = "key"
    settings.models.openai.MODEL = "model"

    session = create_agent_session(settings)

    assert "## system: system.user_configured\nBase prompt." in session.system_prompt
    assert "## skills: skill.focus.0\nFocus on agents." in session.system_prompt
    assert "## runtime_policy: runtime.tool_contract" in session.system_prompt
    assert session.runtime.enabled_tools == ["base_tool", "skill_tool"]
    assert session.workspace.tenant_id == "default"
    assert session.workspace.user_id == "anonymous"
    assert session.workspace.agent_id == "default"
    assert session.workspace.workspace_id == "default"
    assert any(item.id == "skill.focus.0" and item.included for item in session.context_trace)


def test_create_session_respects_explicit_enabled_tools(tmp_path, monkeypatch):
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "focus.json").write_text(
        json.dumps({"name": "focus", "tools": ["skill_tool"]}),
        encoding="utf-8",
    )
    monkeypatch.setattr("agent.assembly.session.ModelClient", lambda config: FakeRuntimeClient())
    settings = FakeSettings()
    settings.server.ROOT_PATH = tmp_path
    settings.agent.SKILLS = "focus"
    settings.models.openai.API_KEY = "key"
    settings.models.openai.MODEL = "model"

    session = create_agent_session(settings, enabled_tools=["explicit_tool"])

    assert session.runtime.enabled_tools == ["explicit_tool"]


def test_create_session_accepts_agent_spec(tmp_path, monkeypatch):
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "focus.json").write_text(
        json.dumps({"name": "focus", "tools": ["skill_tool"]}),
        encoding="utf-8",
    )
    monkeypatch.setattr("agent.assembly.session.ModelClient", lambda config: FakeRuntimeClient())
    settings = FakeSettings()
    settings.server.ROOT_PATH = tmp_path
    settings.models.openai.API_KEY = "key"
    settings.models.openai.MODEL = "settings-model"
    spec = AgentSpec.from_overrides(
        provider="openai-chat",
        model="spec-model",
        agent_id="agent 1",
        user_id="user 1",
        skills=["focus"],
    )

    session = create_agent_session(settings, spec=spec)

    assert session.runtime.model == "spec-model"
    assert session.runtime.enabled_tools == ["skill_tool"]
    assert session.workspace.user_id == "user-1"
    assert session.workspace.agent_id == "agent-1"


def test_create_session_loads_workspace_agents_md(tmp_path, monkeypatch):
    monkeypatch.setattr("agent.assembly.session.ModelClient", lambda config: FakeRuntimeClient())
    settings = FakeSettings()
    settings.server.ROOT_PATH = tmp_path
    settings.models.openai.API_KEY = "key"
    settings.models.openai.MODEL = "model"
    workspace = tmp_path / ".agents" / "workspaces" / "default" / "user-1" / "agent-1" / "default"
    workspace.mkdir(parents=True)
    (workspace / "AGENTS.md").write_text("Workspace instruction.", encoding="utf-8")

    session = create_agent_session(settings, user_id="user 1", agent_id="agent 1")

    assert session.workspace.tenant_id == "default"
    assert session.workspace.user_id == "user-1"
    assert session.workspace.agent_id == "agent-1"
    assert session.workspace.workspace_id == "default"
    assert "## project_instructions: workspace.agents\nWorkspace instruction." in session.system_prompt


def test_async_create_session_can_run_inside_event_loop(tmp_path, monkeypatch):
    from agent.factory import create_agent_session_async

    monkeypatch.setattr("agent.assembly.session.ModelClient", lambda config: FakeRuntimeClient())
    settings = FakeSettings()
    settings.server.ROOT_PATH = tmp_path
    settings.models.openai.API_KEY = "key"
    settings.models.openai.MODEL = "model"

    async def create():
        return await create_agent_session_async(settings)

    session = asyncio.run(create())

    assert session.runtime.provider == "openai-chat"
    assert session.workspace.path.exists()
