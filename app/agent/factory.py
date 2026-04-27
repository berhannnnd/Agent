# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：factory.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from __future__ import annotations

import shlex
from typing import Any, List, Optional

from app.agent.providers import ModelClient, ModelClientConfig
from app.agent.runtime import AgentRuntime, AgentSession
from app.agent.skills import SkillLoader, SkillRegistry
from app.agent.tools.mcp import MCPServerConfig, MCPStdioClient, MCPToolProvider
from app.agent.tools.registry import ToolRegistry


class AgentConfigError(ValueError):
    """Raised when agent runtime config is incomplete."""


def create_agent_session(
    settings: Any,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    system_prompt: Optional[str] = None,
    enabled_tools: Optional[List[str]] = None,
) -> AgentSession:
    config = resolve_model_client_config(settings, provider=provider, model=model, base_url=base_url, api_key=api_key)
    registry = ToolRegistry(max_concurrent=settings.agent.MAX_CONCURRENT_TOOLS)
    load_configured_skills(settings, registry)
    load_configured_mcp_sync(settings, registry)

    active_tools = enabled_tools if enabled_tools is not None else _csv_setting(settings.agent.ENABLED_TOOLS)
    runtime = AgentRuntime(
        model_client=ModelClient(config),
        tools=registry,
        provider=config.provider,
        model=config.model,
        enabled_tools=active_tools,
        max_tool_iterations=settings.agent.MAX_TOOL_ITERATIONS,
    )
    prompt = settings.agent.SYSTEM_PROMPT if system_prompt is None else system_prompt
    return AgentSession(runtime=runtime, system_prompt=prompt, max_context_tokens=settings.agent.MAX_CONTEXT_TOKENS)


def resolve_model_client_config(
    settings: Any,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> ModelClientConfig:
    active_provider = _normalize(provider or settings.agent.PROVIDER)

    # 根据 provider 选择对应的模型配置
    if active_provider == "claude-messages":
        resolved_api_key = _coalesce(api_key, settings.agent.CLAUDE_API_KEY or settings.models.anthropic.API_KEY)
        resolved_base_url = _coalesce(base_url, settings.agent.CLAUDE_BASE_URL or settings.models.anthropic.BASE_URL)
        resolved_model = _coalesce(model, settings.agent.CLAUDE_MODEL or settings.models.anthropic.MODEL)
    elif active_provider == "gemini":
        resolved_api_key = _coalesce(api_key, settings.models.gemini.API_KEY)
        resolved_base_url = _coalesce(base_url, settings.models.gemini.BASE_URL)
        resolved_model = _coalesce(model, settings.models.gemini.MODEL)
    elif active_provider == "openai-responses":
        resolved_api_key = _coalesce(api_key, settings.models.openai_responses.API_KEY or settings.models.openai.API_KEY)
        resolved_base_url = _coalesce(base_url, settings.models.openai_responses.BASE_URL or settings.models.openai.BASE_URL)
        resolved_model = _coalesce(model, settings.models.openai_responses.MODEL or settings.models.openai.MODEL)
    else:  # openai-chat
        resolved_api_key = _coalesce(api_key, settings.models.openai.API_KEY)
        resolved_base_url = _coalesce(base_url, settings.models.openai.BASE_URL)
        resolved_model = _coalesce(model, settings.models.openai.MODEL)

    if not resolved_api_key or not resolved_model:
        missing = []
        if not resolved_api_key:
            missing.append("API_KEY")
        if not resolved_model:
            missing.append("MODEL")
        raise AgentConfigError("missing agent model configuration: %s" % ", ".join(missing))

    return ModelClientConfig(
        provider=active_provider,
        model=resolved_model,
        api_key=resolved_api_key,
        base_url=resolved_base_url,
        timeout=settings.agent.TIMEOUT,
        max_tokens=settings.agent.MAX_TOKENS,
        proxy_url=_proxy_url(settings),
        max_retries=settings.agent.MAX_RETRIES,
        retry_base_delay=settings.agent.RETRY_BASE_DELAY,
    )


def load_configured_skills(settings: Any, registry: ToolRegistry) -> SkillRegistry:
    skill_names = _csv_setting(settings.agent.SKILLS)
    if not skill_names:
        return SkillRegistry([])
    skill_registry = SkillRegistry.load(SkillLoader(settings.server.ROOT_PATH), skill_names)
    return skill_registry


def load_configured_mcp_sync(settings: Any, registry: ToolRegistry) -> None:
    import asyncio

    command = settings.mcp.SERVER_COMMAND
    if not command:
        return
    server = MCPServerConfig(
        name=settings.mcp.SERVER_NAME or "default",
        command=shlex.split(command)[0],
        args=shlex.split(command)[1:],
        timeout_seconds=settings.mcp.CLIENT_TIMEOUT,
    )
    provider = MCPToolProvider(client=MCPStdioClient(server), server=server)
    try:
        asyncio.run(provider.load_tools(registry))
    except RuntimeError:
        loop = asyncio.get_event_loop()
        loop.run_until_complete(provider.load_tools(registry))


def _coalesce(override: Optional[str], configured: Any) -> str:
    value = configured if override is None else override
    return str(value).strip() if value is not None else ""


def _normalize(value: str) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"openai", "chat", "openai-chat-completions"}:
        return "openai-chat"
    if normalized in {"responses", "response"}:
        return "openai-responses"
    if normalized in {"anthropic", "claude"}:
        return "claude-messages"
    if normalized in {"google", "gemini-generate-content"}:
        return "gemini"
    return normalized or "openai-chat"


def _csv_setting(raw: str) -> List[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def _proxy_url(settings: Any) -> str:
    for attr in ("HTTPS_PROXY", "ALL_PROXY", "HTTP_PROXY"):
        value = _coalesce(None, getattr(settings.agent, attr, ""))
        if value:
            return value
    return ""
