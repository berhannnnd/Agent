from __future__ import annotations

import asyncio
from typing import Any, List, Optional

from agent.config import resolve_model_client_config
from agent.context.builder import ContextBuilder
from agent.context.sources import build_context_pack
from agent.definitions import AgentSpec
from agent.hooks import AgentHooks, hooks_from_settings
from agent.integrations import load_configured_mcp, load_configured_skills, resolve_active_tools
from agent.models import ModelClient
from agent.runtime import AgentRuntime, AgentSession
from agent.storage.factory import resolve_workspace
from agent.tools.registry import ToolRegistry


async def create_agent_session_async(
    settings: Any,
    spec: Optional[AgentSpec] = None,
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
    skills: Optional[List[str]] = None,
) -> AgentSession:
    resolved_spec = _resolve_spec(
        spec,
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        system_prompt=system_prompt,
        enabled_tools=enabled_tools,
        tenant_id=tenant_id,
        user_id=user_id,
        agent_id=agent_id,
        workspace_id=workspace_id,
        skills=skills,
    )
    config = resolve_model_client_config(
        settings,
        provider=resolved_spec.model.provider,
        model=resolved_spec.model.model,
        base_url=resolved_spec.model.base_url,
        api_key=resolved_spec.model.api_key,
    )
    registry = ToolRegistry(max_concurrent=settings.agent.MAX_CONCURRENT_TOOLS, tool_timeout=settings.agent.TOOL_TIMEOUT)
    skill_registry = load_configured_skills(settings, skill_names=resolved_spec.skills)
    await load_configured_mcp(settings, registry)

    active_tools = resolve_active_tools(settings, skill_registry, resolved_spec.enabled_tools)
    workspace = resolve_workspace(
        settings,
        tenant_id=resolved_spec.workspace.tenant_id,
        user_id=resolved_spec.workspace.user_id,
        agent_id=resolved_spec.workspace.agent_id,
        workspace_id=resolved_spec.workspace.workspace_id,
    )
    context_pack = build_context_pack(
        system_prompt=settings.agent.SYSTEM_PROMPT if resolved_spec.system_prompt is None else resolved_spec.system_prompt,
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


def create_agent_session(*args: Any, **kwargs: Any) -> AgentSession:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(create_agent_session_async(*args, **kwargs))
    raise RuntimeError("create_agent_session cannot run inside an active event loop; use create_agent_session_async")


def _resolve_spec(
    spec: Optional[AgentSpec],
    *,
    provider: Optional[str] = None,
    model: Optional[str] = None,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    system_prompt: Optional[str] = None,
    enabled_tools: Optional[List[str]] = None,
    tenant_id: str = "",
    user_id: str = "",
    agent_id: str = "",
    workspace_id: str = "",
    skills: Optional[List[str]] = None,
) -> AgentSpec:
    if spec is not None:
        return spec.with_workspace_defaults()
    return AgentSpec.from_overrides(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        system_prompt=system_prompt,
        enabled_tools=enabled_tools,
        tenant_id=tenant_id,
        user_id=user_id,
        agent_id=agent_id,
        workspace_id=workspace_id,
        skills=skills,
    ).with_workspace_defaults()
