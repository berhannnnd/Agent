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
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Optional

from agent.schema import ToolCall, ToolResult, ToolSpec
from agent.capabilities.tools.recording import ToolExecutionObserver, ToolExecutionScope

ToolHandler = Callable[..., Any]


@dataclass(frozen=True)
class RegisteredTool:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: ToolHandler
    metadata: Dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    def __init__(
        self,
        max_concurrent: int = 10,
        tool_timeout: float = 60.0,
        execution_observer: ToolExecutionObserver | None = None,
    ):
        self._tools: Dict[str, RegisteredTool] = {}
        self._max_concurrent = max_concurrent
        self._semaphores: Dict[int, asyncio.Semaphore] = {}
        self._tool_timeout = tool_timeout
        self._execution_observer = execution_observer

    def set_execution_observer(self, observer: ToolExecutionObserver | None) -> None:
        self._execution_observer = observer

    def register(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
        handler: ToolHandler,
        metadata: Dict[str, Any] | None = None,
    ) -> None:
        if name in self._tools:
            raise ValueError("tool already registered: %s" % name)
        self._tools[name] = RegisteredTool(name, description, parameters, handler, dict(metadata or {}))

    def names(self) -> List[str]:
        return sorted(self._tools)

    def specs(self, names: Optional[Iterable[str]] = None) -> List[ToolSpec]:
        selected = list(names) if names is not None else self.names()
        return [self._spec_for(name) for name in selected]

    async def execute(
        self,
        name: str,
        arguments: Dict[str, Any],
        *,
        run_id: str = "",
        task_id: str = "",
        tool_call_id: str = "",
    ) -> ToolResult:
        if name not in self._tools:
            return ToolResult(tool_call_id="", name=name, content="unknown tool: %s" % name, is_error=True)
        tool = self._tools[name]
        scope = ToolExecutionScope(
            run_id=str(run_id or ""),
            task_id=str(task_id or ""),
            tool_call_id=str(tool_call_id or ""),
            tool_name=name,
        )
        started_at = time.perf_counter()
        await self._before_tool(scope, arguments)
        try:
            async with self._semaphore_for_running_loop():
                result = await asyncio.wait_for(
                    _call_handler(tool.handler, arguments),
                    timeout=self._tool_timeout,
                )
            metadata = await self._after_tool(scope, arguments, result=result, duration_ms=_duration_ms(started_at))
            return ToolResult(
                tool_call_id="",
                name=name,
                content=_format_tool_result(result),
                raw=_with_metadata(result, metadata),
            )
        except asyncio.TimeoutError:
            metadata = await self._after_tool(
                scope,
                arguments,
                is_error=True,
                error="tool execution timed out",
                duration_ms=_duration_ms(started_at),
            )
            return ToolResult(
                tool_call_id="",
                name=name,
                content="tool execution timed out",
                is_error=True,
                raw=_with_metadata(None, metadata),
            )
        except Exception as exc:  # noqa: BLE001 - tool failures are model-visible tool results.
            metadata = await self._after_tool(
                scope,
                arguments,
                is_error=True,
                error=str(exc),
                duration_ms=_duration_ms(started_at),
            )
            return ToolResult(
                tool_call_id="",
                name=name,
                content=str(exc),
                is_error=True,
                raw=_with_metadata(None, metadata),
            )

    async def execute_many(
        self,
        calls: Iterable[ToolCall],
        *,
        run_id: str = "",
        task_id: str = "",
    ) -> List[ToolResult]:
        call_list = list(calls)

        async def run(call: ToolCall) -> ToolResult:
            result = await self.execute(
                call.name,
                dict(call.arguments),
                run_id=run_id,
                task_id=task_id,
                tool_call_id=call.id,
            )
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
            raw={"metadata": dict(tool.metadata or {})} if tool.metadata else None,
        )

    def _semaphore_for_running_loop(self) -> asyncio.Semaphore:
        loop = asyncio.get_running_loop()
        key = id(loop)
        semaphore = self._semaphores.get(key)
        if semaphore is None:
            semaphore = asyncio.Semaphore(self._max_concurrent)
            self._semaphores[key] = semaphore
        return semaphore

    async def _before_tool(self, scope: ToolExecutionScope, arguments: Dict[str, Any]) -> dict[str, Any]:
        if self._execution_observer is None:
            return {}
        return await self._execution_observer.before_tool(scope, dict(arguments))

    async def _after_tool(
        self,
        scope: ToolExecutionScope,
        arguments: Dict[str, Any],
        *,
        result: Any = None,
        is_error: bool = False,
        error: str = "",
        duration_ms: float = 0.0,
    ) -> dict[str, Any]:
        if self._execution_observer is None:
            return {}
        return await self._execution_observer.after_tool(
            scope,
            dict(arguments),
            result=result,
            is_error=is_error,
            error=error,
            duration_ms=duration_ms,
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


def _duration_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 3)


def _with_metadata(result: Any, metadata: dict[str, Any]) -> Any:
    if not metadata:
        return result
    if isinstance(result, dict):
        payload = dict(result)
        payload["_meta"] = dict(payload.get("_meta") or {})
        payload["_meta"].update(metadata)
        return payload
    return {"result": result, "_meta": dict(metadata)}
