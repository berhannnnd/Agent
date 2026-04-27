from __future__ import annotations

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
