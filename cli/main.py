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
import shlex
import sys
from pathlib import Path
from typing import Annotated, Optional
from uuid import uuid4

import click
import typer

from agent.assembly import create_agent_session as _create_agent_session
from agent.assembly import create_agent_session_async as _create_agent_session_async
from agent.config import (
    AgentConfigError,
    ModelProfile,
    active_profile_name,
    build_model_profiles,
    resolve_model_profile,
    runtime_settings as settings,
)
from agent.config.paths import ENV_FILE
from agent.runtime import InMemoryCheckpointStore
from agent.specs import AgentSpec
from cli.commands import COMMANDS, command_lookup
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
from cli.ui import ChatInput, TerminalUI

client = typer.Typer(rich_markup_mode="rich")


@client.callback()
def root() -> None:
    """Agents terminal interface."""


def create_agent_session(**kwargs):
    runtime_settings = kwargs.pop("settings_override", settings)
    loop = kwargs.pop("loop", None)
    if loop is not None:
        return loop.run_until_complete(_create_agent_session_async(runtime_settings, **kwargs))
    return _create_agent_session(runtime_settings, **kwargs)


@client.command("chat")
def chat(
    model_profile: Annotated[
        Optional[str],
        typer.Option("--model-profile", "-m", help="选择 .env/config 中的模型配置组，例如 openai-chat、kimi。"),
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
    ui = TerminalUI()
    model_profiles = build_model_profiles(runtime_settings)
    chat_input = ChatInput(COMMANDS, model_profiles)
    selected_start_profile = _resolve_start_model_profile(model_profile, model_profiles, ui)
    resolved_user_id = user_id or local_user_id()
    resolved_agent_id = agent_id or "cli"
    resolved_workspace_id = workspace_id or (active_workspace.name if active_workspace else "")
    active_system_prompt = cli_system_prompt(system_prompt, profile_name, active_workspace)
    input_is_tty = sys.stdin.isatty()
    turn_loop = asyncio.new_event_loop()
    previous_loop = None

    def make_session(
        *,
        protocol_override: Optional[str],
        model_override: Optional[str],
        base_url_override: Optional[str],
        api_key_override: Optional[str],
    ):
        return create_agent_session(
            settings_override=runtime_settings,
            loop=turn_loop,
            checkpoint_store=checkpoint_store,
            spec=AgentSpec.from_overrides(
                protocol=protocol_override,
                model=model_override,
                base_url=base_url_override,
                api_key=api_key_override,
                system_prompt=active_system_prompt,
                enabled_tools=active_tools,
                tenant_id=tenant_id or "",
                user_id=resolved_user_id,
                agent_id=resolved_agent_id,
                workspace_id=resolved_workspace_id,
                workspace_path=str(active_workspace) if active_workspace else "",
                permission_profile=permission_mode,
                approval_required_tools=approval_tools,
            ),
        )

    session = None
    try:
        try:
            previous_loop = asyncio.get_event_loop()
        except RuntimeError:
            previous_loop = None
        asyncio.set_event_loop(turn_loop)
        try:
            session = make_session(
                protocol_override=selected_start_profile.protocol if selected_start_profile else None,
                model_override=selected_start_profile.model if selected_start_profile else None,
                base_url_override=selected_start_profile.base_url if selected_start_profile else None,
                api_key_override=selected_start_profile.api_key if selected_start_profile else None,
            )
        except AgentConfigError as exc:
            ui.error(str(exc))
            raise typer.Exit(code=2)

        ui.startup(
            session,
            profile=profile_name,
            permission=permission,
            model_profile=active_profile_name(
                model_profiles,
                session.runtime.protocol,
                session.runtime.model,
                _model_base_url(session),
            ),
            sandbox_provider=str(getattr(runtime_settings.agent, "SANDBOX_PROVIDER", sandbox_provider or "local")),
            tools=getattr(session.runtime, "enabled_tools", []) or [],
        )
        while True:
            try:
                user_message = chat_input.read(ui.user_prompt_label(), ui.user_prompt_suffix()).strip()
            except (EOFError, KeyboardInterrupt, click.Abort):
                ui.newline()
                break
            if not input_is_tty:
                ui.newline()

            if not user_message:
                continue
            if user_message.startswith("/"):
                should_continue, next_session = _handle_command(
                    user_message,
                    session,
                    ui,
                    profile_name,
                    permission,
                    active_tools,
                    model_profiles,
                    active_model_profile=active_profile_name(
                        model_profiles,
                        session.runtime.protocol,
                        session.runtime.model,
                        _model_base_url(session),
                    ),
                    switch_model=lambda selected_profile: _switch_model_session(
                        session,
                        ui,
                        make_session,
                        profile=selected_profile,
                        profiles=model_profiles,
                        close_current=lambda current: _close_session_model_client(turn_loop, current),
                    ),
                )
                session = next_session
                if should_continue:
                    continue
                break

            turn_loop.run_until_complete(print_streaming_turn(session, user_message, run_id=_run_id(), ui=ui))
    finally:
        if session is not None:
            _close_session_model_client(turn_loop, session)
        asyncio.set_event_loop(previous_loop)
        turn_loop.close()


def _handle_command(
    command: str,
    session,
    ui: TerminalUI,
    profile: str,
    permission: str,
    active_tools: list[str],
    model_profiles: list[ModelProfile],
    *,
    active_model_profile: str = "",
    switch_model,
) -> tuple[bool, object]:
    base_command = command.split(maxsplit=1)[0]
    canonical = command_lookup().get(base_command)
    command_name = canonical.name if canonical is not None else base_command
    if command_name == "/exit":
        return False, session
    if command_name == "/help":
        ui.help()
        return True, session
    if command_name == "/clear":
        session.clear()
        ui.notice("cleared")
        return True, session
    if command_name == "/status":
        ui.status(session, profile=profile, permission=permission, tools=active_tools, model_profile=active_model_profile)
        return True, session
    if command_name == "/doctor":
        ui.doctor(
            session,
            profiles=model_profiles,
            tools=active_tools,
            env_file=ENV_FILE,
            model_profile=active_model_profile,
        )
        return True, session
    if command_name in {"/model"}:
        target = _parse_model_command(command, model_profiles=model_profiles)
        if target is None:
            ui.model(session, profiles=model_profiles)
            return True, session
        if target == "list":
            ui.model(session, profiles=model_profiles)
            return True, session
        if not isinstance(target, ModelProfile):
            ui.error(str(target))
            return True, session
        next_session = switch_model(target)
        return True, next_session
    if command_name == "/workspace":
        ui.workspace(session)
        return True, session
    if command_name == "/tools":
        ui.tools(active_tools)
        return True, session
    if command_name == "/context":
        ui.context(session)
        return True, session
    if command_name == "/trace":
        ui.trace(session)
        return True, session
    ui.error("unknown command: %s" % command)
    ui.notice("Run /help to see available commands.")
    return True, session


def _resolve_start_model_profile(name: Optional[str], profiles: list[ModelProfile], ui: TerminalUI) -> ModelProfile | None:
    if not name:
        return None
    profile = resolve_model_profile(profiles, name)
    if profile is None:
        ui.error("unknown model profile: %s. Run /model to see configured profiles." % name)
        raise typer.Exit(code=2)
    return profile


def _parse_model_command(command: str, *, model_profiles: list[ModelProfile]) -> ModelProfile | str | None:
    parts = shlex.split(command)
    if len(parts) <= 1:
        return None
    if parts[1] in {"list", "ls"}:
        return "list"
    if len(parts) > 2:
        return "/model only accepts a configured profile name. Example: /model kimi"
    value = parts[1]
    profile = resolve_model_profile(model_profiles, value)
    if profile is None:
        return "unknown model profile: %s. Run /model to see configured profiles." % value
    return profile


def _switch_model_session(
    session,
    ui: TerminalUI,
    make_session,
    *,
    profile: ModelProfile,
    profiles: list[ModelProfile],
    close_current=None,
):
    try:
        next_session = make_session(
            protocol_override=profile.protocol,
            model_override=profile.model or None,
            base_url_override=profile.base_url or None,
            api_key_override=profile.api_key or None,
        )
    except AgentConfigError as exc:
        ui.error(str(exc))
        return session
    next_session.messages = list(getattr(session, "messages", []))
    if close_current is not None:
        close_current(session)
    ui.model_switched(
        next_session,
        profile=active_profile_name(
            [profile],
            next_session.runtime.protocol,
            next_session.runtime.model,
            _model_base_url(next_session),
        )
        or profile.name,
    )
    ui.model(next_session, profiles=profiles)
    return next_session


def _run_id() -> str:
    return "cli_%s" % uuid4().hex


def _close_session_model_client(loop: asyncio.AbstractEventLoop, session) -> None:
    runtime = getattr(session, "runtime", None)
    model_client = getattr(runtime, "model_client", None)
    close = getattr(model_client, "async_close", None)
    if close is None or loop.is_closed():
        return
    try:
        loop.run_until_complete(close())
    except Exception:
        return


def _model_base_url(session) -> str:
    runtime = getattr(session, "runtime", None)
    model_client = getattr(runtime, "model_client", None)
    config = getattr(model_client, "config", None)
    return str(getattr(config, "base_url", "") or "")


def main() -> None:
    client()


if __name__ == "__main__":
    main()
