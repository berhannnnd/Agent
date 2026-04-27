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
from typing import Annotated, Optional

import click
import typer

from agent.factory import AgentConfigError, create_agent_session as _create_agent_session
from agent.definitions import AgentSpec
from gateway.core.config import settings

client = typer.Typer(rich_markup_mode="rich")


@client.callback()
def root() -> None:
    """Agents terminal interface."""


def create_agent_session(**kwargs):
    return _create_agent_session(settings, **kwargs)


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
    try:
        session = create_agent_session(
            spec=AgentSpec.from_overrides(
                provider=provider,
                model=model,
                base_url=base_url,
                api_key=api_key,
                system_prompt=system_prompt,
                tenant_id=tenant_id or "",
                user_id=user_id or "",
                agent_id=agent_id or "",
                workspace_id=workspace_id or "",
            )
        )
    except AgentConfigError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=2)

    typer.echo("agent provider: %s/%s" % (session.runtime.provider, session.runtime.model))
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

        asyncio.run(_print_streaming_turn(session, user_message))


async def _print_streaming_turn(session, user_message: str) -> None:
    wrote_text = False
    try:
        async for event in session.stream(user_message):
            if event.type == "text_delta":
                if not wrote_text:
                    typer.echo("assistant> ", nl=False)
                    wrote_text = True
                typer.echo(event.payload.get("delta", ""), nl=False)
            elif event.type == "tool_start":
                if wrote_text:
                    typer.echo()
                    wrote_text = False
                typer.echo("tool> %s" % event.name)
            elif event.type == "tool_result":
                typer.echo("tool result> %s: %s" % (event.name, event.payload.get("content", "")))
            elif event.type == "done":
                if wrote_text:
                    typer.echo()
                    wrote_text = False
                elif event.payload.get("content"):
                    typer.echo("assistant> %s" % event.payload["content"])
    except Exception as exc:  # noqa: BLE001 - terminal chat should keep running after one bad turn.
        if wrote_text:
            typer.echo()
        typer.echo("error: %s" % exc)


def main() -> None:
    client()


if __name__ == "__main__":
    main()
