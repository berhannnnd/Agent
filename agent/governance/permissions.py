from __future__ import annotations

import inspect
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Iterable, Protocol, Union

from agent.schema import ToolCall


@dataclass(frozen=True)
class ToolPermissionDecision:
    allowed: bool
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    requires_approval: bool = False

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "allowed": self.allowed,
            "requires_approval": self.requires_approval,
        }
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


class DenyAllToolPermissionPolicy:
    async def authorize(self, call: ToolCall) -> ToolPermissionDecision:
        return ToolPermissionDecision(allowed=False, reason="tool execution disabled by policy")


class StaticToolPermissionPolicy:
    def __init__(
        self,
        allowed_tools: Iterable[str] | None = None,
        denied_tools: Iterable[str] | None = None,
        approval_required_tools: Iterable[str] | None = None,
        require_approval_for_all: bool = False,
    ):
        self.restrict_allowed_tools = allowed_tools is not None
        self.allowed_tools = set(allowed_tools or [])
        self.denied_tools = set(denied_tools or [])
        self.approval_required_tools = set(approval_required_tools or [])
        self.require_approval_for_all = require_approval_for_all

    async def authorize(self, call: ToolCall) -> ToolPermissionDecision:
        if call.name in self.denied_tools:
            return ToolPermissionDecision(allowed=False, reason="tool denied by policy")
        if self.restrict_allowed_tools and call.name not in self.allowed_tools:
            return ToolPermissionDecision(allowed=False, reason="tool is not in the allowed tool set")
        if self.require_approval_for_all or call.name in self.approval_required_tools:
            return ToolPermissionDecision(
                allowed=False,
                reason="tool requires user approval",
                requires_approval=True,
                metadata={"permission": "ask"},
            )
        return ToolPermissionDecision(allowed=True)


PermissionResult = Union[bool, ToolPermissionDecision]
PermissionHandler = Callable[[ToolCall], Union[PermissionResult, Awaitable[PermissionResult]]]


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
