# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：test_agent_factory.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

import pytest

from app.agent.factory import AgentConfigError, resolve_model_client_config


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
    TIMEOUT = 60.0
    MAX_TOKENS = 4096
    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 1.0
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
