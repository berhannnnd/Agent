from __future__ import annotations

import asyncio
import shlex
from typing import Any

from agent.tools.mcp import MCPServerConfig, MCPStdioClient, MCPToolProvider
from agent.tools.registry import ToolRegistry


async def load_configured_mcp(settings: Any, registry: ToolRegistry) -> None:
    command = str(settings.mcp.SERVER_COMMAND or "").strip()
    if not command:
        return
    command_parts = shlex.split(command)
    server = MCPServerConfig(
        name=settings.mcp.SERVER_NAME or "default",
        command=command_parts[0],
        args=command_parts[1:],
        timeout_seconds=settings.mcp.CLIENT_TIMEOUT,
    )
    provider = MCPToolProvider(client=MCPStdioClient(server), server=server)
    await provider.load_tools(registry)


def load_configured_mcp_sync(settings: Any, registry: ToolRegistry) -> None:
    if not str(settings.mcp.SERVER_COMMAND or "").strip():
        return
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(load_configured_mcp(settings, registry))
        return
    raise RuntimeError("load_configured_mcp_sync cannot run inside an active event loop")
