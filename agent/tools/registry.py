# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：registry.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from __future__ import annotations

import asyncio
import inspect
import json
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional

from agent.schema import ToolCall, ToolResult, ToolSpec

ToolHandler = Callable[..., Any]


@dataclass(frozen=True)
class RegisteredTool:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: ToolHandler


class ToolRegistry:
    def __init__(self, max_concurrent: int = 10, tool_timeout: float = 60.0):
        self._tools: Dict[str, RegisteredTool] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._tool_timeout = tool_timeout

    def register(self, name: str, description: str, parameters: Dict[str, Any], handler: ToolHandler) -> None:
        if name in self._tools:
            raise ValueError("tool already registered: %s" % name)
        self._tools[name] = RegisteredTool(name, description, parameters, handler)

    def names(self) -> List[str]:
        return sorted(self._tools)

    def specs(self, names: Optional[Iterable[str]] = None) -> List[ToolSpec]:
        selected = list(names) if names is not None else self.names()
        return [self._spec_for(name) for name in selected]

    async def execute(self, name: str, arguments: Dict[str, Any]) -> ToolResult:
        if name not in self._tools:
            return ToolResult(tool_call_id="", name=name, content="unknown tool: %s" % name, is_error=True)
        tool = self._tools[name]
        try:
            async with self._semaphore:
                result = await asyncio.wait_for(
                    _call_handler(tool.handler, arguments),
                    timeout=self._tool_timeout,
                )
            return ToolResult(tool_call_id="", name=name, content=_format_tool_result(result), raw=result)
        except asyncio.TimeoutError:
            return ToolResult(tool_call_id="", name=name, content="tool execution timed out", is_error=True)
        except Exception as exc:  # noqa: BLE001 - tool failures are model-visible tool results.
            return ToolResult(tool_call_id="", name=name, content=str(exc), is_error=True)

    async def execute_many(self, calls: Iterable[ToolCall]) -> List[ToolResult]:
        call_list = list(calls)

        async def run(call: ToolCall) -> ToolResult:
            result = await self.execute(call.name, dict(call.arguments))
            return ToolResult(
                tool_call_id=call.id,
                name=call.name,
                content=result.content,
                is_error=result.is_error,
                raw=result.raw,
            )

        return list(await asyncio.gather(*(run(call) for call in call_list)))

    def _spec_for(self, name: str) -> ToolSpec:
        if name not in self._tools:
            raise KeyError("unknown tool: %s" % name)
        tool = self._tools[name]
        return ToolSpec(
            name=tool.name,
            description=tool.description,
            parameters=tool.parameters,
            source="registry",
        )


async def _call_handler(handler: ToolHandler, arguments: Dict[str, Any]) -> Any:
    result = handler(**arguments)
    if inspect.isawaitable(result):
        result = await result
    return result


def _format_tool_result(result: Any) -> str:
    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False, sort_keys=True)
