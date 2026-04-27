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
from pathlib import Path
from typing import Any, List, Optional

from agent.hooks import AgentHooks, hooks_from_settings
from agent.context import ContextBuilder, build_context_pack
from agent.models import ModelClient, ModelClientConfig
from agent.models.constants import normalize_provider
from agent.runtime import AgentRuntime, AgentSession
from agent.skills import SkillLoader, SkillRegistry
from agent.storage import LocalWorkspaceStore
from agent.tools.mcp import MCPServerConfig, MCPStdioClient, MCPToolProvider
from agent.tools.registry import ToolRegistry


class AgentConfigError(ValueError):
    """Raised when agent runtime config is incomplete."""


# provider → 配置属性优先级列表（从高到低）
_PROVIDER_CONFIG_SOURCES: dict[str, dict[str, list[str]]] = {
    "claude-messages": {
        "api_key": ["agent.CLAUDE_API_KEY", "models.anthropic.API_KEY"],
        "base_url": ["agent.CLAUDE_BASE_URL", "models.anthropic.BASE_URL"],
        "model": ["agent.CLAUDE_MODEL", "models.anthropic.MODEL"],
    },
    "gemini": {
        "api_key": ["models.gemini.API_KEY"],
        "base_url": ["models.gemini.BASE_URL"],
        "model": ["models.gemini.MODEL"],
    },
    "openai-responses": {
        "api_key": ["models.openai_responses.API_KEY", "models.openai.API_KEY"],
        "base_url": ["models.openai_responses.BASE_URL", "models.openai.BASE_URL"],
        "model": ["models.openai_responses.MODEL", "models.openai.MODEL"],
    },
    "openai-chat": {
        "api_key": ["models.openai.API_KEY"],
        "base_url": ["models.openai.BASE_URL"],
        "model": ["models.openai.MODEL"],
    },
}


def create_agent_session(
    settings: Any,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    system_prompt: Optional[str] = None,
    enabled_tools: Optional[List[str]] = None,
    hooks: Optional[AgentHooks] = None,
    tenant_id: str = "",
    user_id: str = "",
    agent_id: str = "",
    workspace_id: str = "",
) -> AgentSession:
    config = resolve_model_client_config(settings, provider=provider, model=model, base_url=base_url, api_key=api_key)
    registry = ToolRegistry(max_concurrent=settings.agent.MAX_CONCURRENT_TOOLS, tool_timeout=settings.agent.TOOL_TIMEOUT)
    skill_registry = load_configured_skills(settings)
    load_configured_mcp_sync(settings, registry)

    active_tools = _resolve_active_tools(settings, skill_registry, enabled_tools)
    workspace = _resolve_workspace(
        settings,
        tenant_id=tenant_id,
        user_id=user_id,
        agent_id=agent_id,
        workspace_id=workspace_id,
    )
    context_pack = build_context_pack(
        system_prompt=settings.agent.SYSTEM_PROMPT if system_prompt is None else system_prompt,
        skill_registry=skill_registry,
        enabled_tools=active_tools,
        workspace=workspace,
    )
    compiled_context = ContextBuilder().compile(context_pack, budget_tokens=settings.agent.MAX_CONTEXT_TOKENS)
    active_hooks = hooks if hooks is not None else hooks_from_settings(settings)
    runtime = AgentRuntime(
        model_client=ModelClient(config),
        tools=registry,
        provider=config.provider,
        model=config.model,
        enabled_tools=active_tools,
        max_tool_iterations=settings.agent.MAX_TOOL_ITERATIONS,
        hooks=active_hooks,
    )
    return AgentSession(
        runtime=runtime,
        system_prompt=compiled_context.system_text,
        max_context_tokens=settings.agent.MAX_CONTEXT_TOKENS,
        context_trace=compiled_context.trace,
        workspace=workspace,
    )


def resolve_model_client_config(
    settings: Any,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
) -> ModelClientConfig:
    active_provider = normalize_provider(provider or settings.agent.PROVIDER)
    sources = _PROVIDER_CONFIG_SOURCES.get(active_provider, _PROVIDER_CONFIG_SOURCES["openai-chat"])

    resolved_api_key = _coalesce(api_key, _resolve_config_value(settings, sources["api_key"]))
    resolved_base_url = _coalesce(base_url, _resolve_config_value(settings, sources["base_url"]))
    resolved_model = _coalesce(model, _resolve_config_value(settings, sources["model"]))

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


def _resolve_config_value(settings: Any, attr_paths: list[str]) -> str:
    """按优先级列表读取嵌套配置属性，返回第一个非空值。"""
    for path in attr_paths:
        value = settings
        for part in path.split("."):
            value = getattr(value, part, None)
            if value is None:
                break
        if value is not None:
            result = str(value).strip()
            if result:
                return result
    return ""


def load_configured_skills(settings: Any) -> SkillRegistry:
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


def _csv_setting(raw: str) -> List[str]:
    return [item.strip() for item in str(raw or "").split(",") if item.strip()]


def _resolve_active_tools(
    settings: Any,
    skill_registry: SkillRegistry,
    enabled_tools: Optional[List[str]] = None,
) -> List[str]:
    if enabled_tools is not None:
        return list(enabled_tools)
    return _merge_unique(_csv_setting(settings.agent.ENABLED_TOOLS), skill_registry.tool_names())


def _merge_unique(*groups: List[str]) -> List[str]:
    names: List[str] = []
    seen = set()
    for group in groups:
        for name in group:
            if name not in seen:
                seen.add(name)
                names.append(name)
    return names


def _resolve_workspace(
    settings: Any,
    tenant_id: str = "",
    user_id: str = "",
    agent_id: str = "",
    workspace_id: str = "",
):
    configured_root = Path(str(getattr(settings.agent, "WORKSPACE_ROOT", ".agents/workspaces")))
    root = configured_root if configured_root.is_absolute() else Path(settings.server.ROOT_PATH) / configured_root
    return LocalWorkspaceStore(root).allocate(
        tenant_id=tenant_id,
        user_id=user_id,
        agent_id=agent_id,
        workspace_id=workspace_id,
        create=True,
    )


def _proxy_url(settings: Any) -> str:
    for attr in ("HTTPS_PROXY", "ALL_PROXY", "HTTP_PROXY"):
        value = _coalesce(None, getattr(settings.agent, attr, ""))
        if value:
            return value
    return ""
