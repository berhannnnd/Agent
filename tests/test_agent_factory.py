# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：test_agent_factory.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

import json

import pytest

from agent.factory import AgentConfigError, create_agent_session, resolve_model_client_config


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
    monkeypatch.setattr("agent.factory.ModelClient", lambda config: FakeRuntimeClient())
    settings = FakeSettings()
    settings.server.ROOT_PATH = tmp_path
    settings.agent.SYSTEM_PROMPT = "Base prompt."
    settings.agent.SKILLS = "focus"
    settings.agent.ENABLED_TOOLS = "base_tool"
    settings.models.openai.API_KEY = "key"
    settings.models.openai.MODEL = "model"

    session = create_agent_session(settings)

    assert session.system_prompt == "Base prompt.\n\nFocus on agents."
    assert session.runtime.enabled_tools == ["base_tool", "skill_tool"]


def test_create_session_respects_explicit_enabled_tools(tmp_path, monkeypatch):
    (tmp_path / "skills").mkdir()
    (tmp_path / "skills" / "focus.json").write_text(
        json.dumps({"name": "focus", "tools": ["skill_tool"]}),
        encoding="utf-8",
    )
    monkeypatch.setattr("agent.factory.ModelClient", lambda config: FakeRuntimeClient())
    settings = FakeSettings()
    settings.server.ROOT_PATH = tmp_path
    settings.agent.SKILLS = "focus"
    settings.models.openai.API_KEY = "key"
    settings.models.openai.MODEL = "model"

    session = create_agent_session(settings, enabled_tools=["explicit_tool"])

    assert session.runtime.enabled_tools == ["explicit_tool"]
