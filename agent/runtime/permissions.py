from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Iterable, Protocol

from agent.schema import ToolCall


@dataclass(frozen=True)
class ToolPermissionDecision:
    allowed: bool
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"allowed": self.allowed}
        if self.reason:
            payload["reason"] = self.reason
        if self.metadata:
            payload["metadata"] = dict(self.metadata)
        return payload


class ToolPermissionPolicy(Protocol):
    async def authorize(self, call: ToolCall) -> ToolPermissionDecision:
        raise NotImplementedError()


class AllowAllToolPermissionPolicy:
    async def authorize(self, call: ToolCall) -> ToolPermissionDecision:
        return ToolPermissionDecision(allowed=True)


class StaticToolPermissionPolicy:
    def __init__(self, allowed_tools: Iterable[str] | None = None, denied_tools: Iterable[str] | None = None):
        self.allowed_tools = set(allowed_tools or [])
        self.denied_tools = set(denied_tools or [])

    async def authorize(self, call: ToolCall) -> ToolPermissionDecision:
        if call.name in self.denied_tools:
            return ToolPermissionDecision(allowed=False, reason="tool denied by policy")
        if self.allowed_tools and call.name not in self.allowed_tools:
            return ToolPermissionDecision(allowed=False, reason="tool is not in the allowed tool set")
        return ToolPermissionDecision(allowed=True)


PermissionHandler = Callable[[ToolCall], bool | ToolPermissionDecision | Awaitable[bool | ToolPermissionDecision]]


class CallbackToolPermissionPolicy:
    def __init__(self, handler: PermissionHandler):
        self.handler = handler

    async def authorize(self, call: ToolCall) -> ToolPermissionDecision:
        result = self.handler(call)
        if inspect.isawaitable(result):
            result = await result
        if isinstance(result, ToolPermissionDecision):
            return result
        return ToolPermissionDecision(allowed=bool(result))
