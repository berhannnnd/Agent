# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：mcp.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Protocol

from agent.capabilities.tools.registry import ToolRegistry


@dataclass(frozen=True)
class MCPServerConfig:
    name: str
    command: str = ""
    args: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    timeout_seconds: float = 30.0
    execution_mode: str = "trusted_control_plane"
    sandbox_profile: str = ""


@dataclass(frozen=True)
class MCPToolDefinition:
    name: str
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)


class MCPClient(Protocol):
    async def list_tools(self) -> List[MCPToolDefinition]:
        raise NotImplementedError()

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        raise NotImplementedError()

    async def close(self) -> None:
        raise NotImplementedError()


class MCPStdioClient:
    def __init__(self, server: MCPServerConfig):
        self.server = server
        self._stdio_context: Optional[Any] = None
        self._session_context: Optional[Any] = None
        self._session: Optional[Any] = None

    async def initialize(self) -> None:
        if self._session is not None:
            return
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        command = shutil.which(self.server.command) if self.server.command else None
        command = command or self.server.command
        params = StdioServerParameters(
            command=command,
            args=self.server.args,
            env={**os.environ, **self.server.env} if self.server.env else None,
        )
        self._stdio_context = stdio_client(params)
        read, write = await self._stdio_context.__aenter__()
        self._session_context = ClientSession(read, write)
        self._session = await self._session_context.__aenter__()
        await self._session.initialize()

    async def list_tools(self) -> List[MCPToolDefinition]:
        await self.initialize()
        response = await self._session.list_tools()
        raw_tools = getattr(response, "tools", None)
        if raw_tools is None:
            raw_tools = []
            for item in response:
                if isinstance(item, tuple) and item[0] == "tools":
                    raw_tools.extend(item[1])
        return [
            MCPToolDefinition(
                name=tool.name,
                description=getattr(tool, "description", "") or "",
                parameters=dict(getattr(tool, "inputSchema", None) or getattr(tool, "input_schema", None) or {}),
            )
            for tool in raw_tools
        ]

    async def call_tool(self, name: str, arguments: Dict[str, Any]) -> Any:
        await self.initialize()
        result = await self._session.call_tool(name, arguments)
        return _format_mcp_result(result)

    async def close(self) -> None:
        if self._session_context is not None:
            await self._session_context.__aexit__(None, None, None)
            self._session_context = None
            self._session = None
        if self._stdio_context is not None:
            await self._stdio_context.__aexit__(None, None, None)
            self._stdio_context = None


@dataclass(frozen=True)
class MCPToolProvider:
    client: MCPClient
    server: MCPServerConfig

    async def load_tools(self, registry: ToolRegistry) -> None:
        for tool in await self.client.list_tools():
            registry.register(
                self._registry_name(tool.name),
                tool.description,
                tool.parameters,
                self._handler(tool.name),
                metadata={
                    "source": "mcp",
                    "server": self.server.name,
                    "remote_name": tool.name,
                    "execution_mode": self.server.execution_mode,
                    "sandbox_profile": self.server.sandbox_profile,
                    "risk": "medium",
                },
            )

    def _registry_name(self, name: str) -> str:
        return "mcp_%s_%s" % (self.server.name, name)

    def _handler(self, remote_name: str):
        async def call_remote(**arguments: Any) -> str:
            result = await self.client.call_tool(remote_name, dict(arguments))
            if isinstance(result, str):
                return result
            return json.dumps(result, ensure_ascii=False, sort_keys=True)

        return call_remote

    async def close(self) -> None:
        close = getattr(self.client, "close", None)
        if close is not None:
            await close()


def _format_mcp_result(result: Any) -> Any:
    content = getattr(result, "content", None)
    if content is None and isinstance(result, dict):
        content = result.get("content")
    if not content:
        return result
    parts: List[str] = []
    for item in content:
        item_type = getattr(item, "type", None) or (item.get("type") if isinstance(item, dict) else "")
        if item_type == "text":
            parts.append(getattr(item, "text", None) or item.get("text", ""))
        else:
            parts.append(json.dumps(item, ensure_ascii=False, sort_keys=True, default=str))
    return "\n".join(part for part in parts if part)
