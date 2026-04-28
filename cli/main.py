# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：cli.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated, Optional
from uuid import uuid4

import click
import typer

from agent.assembly import create_agent_session as _create_agent_session
from agent.config import AgentConfigError
from agent.runtime import InMemoryCheckpointStore
from agent.specs import AgentSpec
from cli.profiles import (
    enabled_tools,
    local_user_id,
    normalize_profile,
    permission_settings,
    settings_for_cli,
    system_prompt as cli_system_prompt,
    workspace_path as resolve_cli_workspace_path,
)
from cli.turns import print_streaming_turn
from gateway.core.config import settings

client = typer.Typer(rich_markup_mode="rich")


@client.callback()
def root() -> None:
    """Agents terminal interface."""


def create_agent_session(**kwargs):
    runtime_settings = kwargs.pop("settings_override", settings)
    return _create_agent_session(runtime_settings, **kwargs)


@client.command("chat")
def chat(
    provider: Annotated[
        Optional[str],
        typer.Option("--provider", "-p", help="模型 provider: openai-chat/openai-responses/claude-messages/gemini。"),
    ] = None,
    model: Annotated[
        Optional[str],
        typer.Option("--model", "-m", help="覆盖模型名。"),
    ] = None,
    base_url: Annotated[
        Optional[str],
        typer.Option("--base-url", help="覆盖 provider base URL。"),
    ] = None,
    api_key: Annotated[
        Optional[str],
        typer.Option("--api-key", help="覆盖 provider API key。"),
    ] = None,
    system_prompt: Annotated[
        Optional[str],
        typer.Option("--system", help="本次会话的 system prompt。"),
    ] = None,
    profile: Annotated[
        str,
        typer.Option("--profile", help="CLI profile: coding/chat/browser。coding 默认绑定当前目录并启用本地代码工具。"),
    ] = "coding",
    tools: Annotated[
        Optional[str],
        typer.Option("--tools", help="逗号分隔的启用工具列表；不传则使用 profile 默认工具。"),
    ] = None,
    permission: Annotated[
        str,
        typer.Option("--permission", help="工具权限: guarded/auto/ask/deny。guarded 会自动读，写入和执行前确认。"),
    ] = "guarded",
    workspace_path: Annotated[
        Optional[Path],
        typer.Option("--workspace-path", help="本地工作区路径；coding/browser 默认当前目录。"),
    ] = None,
    sandbox_provider: Annotated[
        Optional[str],
        typer.Option("--sandbox-provider", help="local 或 docker；不传使用配置默认值。"),
    ] = None,
    tenant_id: Annotated[
        Optional[str],
        typer.Option("--tenant-id", help="用于解析本地工作区的租户 ID。"),
    ] = None,
    user_id: Annotated[
        Optional[str],
        typer.Option("--user-id", help="用于解析本地工作区的用户 ID。"),
    ] = None,
    agent_id: Annotated[
        Optional[str],
        typer.Option("--agent-id", help="用于解析本地工作区的智能体 ID。"),
    ] = None,
    workspace_id: Annotated[
        Optional[str],
        typer.Option("--workspace-id", help="用于解析本地工作区的 workspace ID。"),
    ] = None,
):
    """打开完整 agent 终端聊天窗口。"""
    profile_name = normalize_profile(profile)
    active_workspace = resolve_cli_workspace_path(profile_name, workspace_path)
    active_tools = enabled_tools(profile_name, tools)
    permission_mode, approval_tools = permission_settings(permission, profile_name)
    runtime_settings = settings_for_cli(profile_name, sandbox_provider)
    checkpoint_store = InMemoryCheckpointStore()
    try:
        session = create_agent_session(
            settings_override=runtime_settings,
            checkpoint_store=checkpoint_store,
            spec=AgentSpec.from_overrides(
                provider=provider,
                model=model,
                base_url=base_url,
                api_key=api_key,
                system_prompt=cli_system_prompt(system_prompt, profile_name, active_workspace),
                enabled_tools=active_tools,
                tenant_id=tenant_id or "",
                user_id=user_id or local_user_id(),
                agent_id=agent_id or "cli",
                workspace_id=workspace_id or (active_workspace.name if active_workspace else ""),
                workspace_path=str(active_workspace) if active_workspace else "",
                permission_profile=permission_mode,
                approval_required_tools=approval_tools,
            )
        )
    except AgentConfigError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=2)

    typer.echo("agent provider: %s/%s" % (session.runtime.provider, session.runtime.model))
    if getattr(session, "workspace", None) is not None:
        typer.echo("workspace: %s" % session.workspace.path)
    typer.echo("tools: %s" % ", ".join(getattr(session.runtime, "enabled_tools", []) or []))
    typer.echo("commands: /exit, /quit, /clear")

    while True:
        try:
            user_message = typer.prompt("user", prompt_suffix="> ").strip()
        except (EOFError, KeyboardInterrupt, click.Abort):
            typer.echo()
            break

        if not user_message:
            continue
        if user_message in {"/exit", "/quit"}:
            break
        if user_message == "/clear":
            session.clear()
            typer.echo("cleared")
            continue

        asyncio.run(print_streaming_turn(session, user_message, run_id=_run_id()))


def _run_id() -> str:
    return "cli_%s" % uuid4().hex


def main() -> None:
    client()


if __name__ == "__main__":
    main()
