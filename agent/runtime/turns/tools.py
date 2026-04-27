from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Iterable, List

from agent.hooks import AgentHooks
from agent.security.permissions import AllowAllToolPermissionPolicy, ToolPermissionDecision, ToolPermissionPolicy
from agent.runtime.events import tool_result_event
from agent.schema import Message, RuntimeEvent, ToolCall, ToolResult
from agent.tools.registry import ToolRegistry


@dataclass(frozen=True)
class ToolExecutionBatch:
    results: List[ToolResult]
    events: List[RuntimeEvent]
    messages: List[Message]


class ToolOrchestrator:
    """Executes model-requested tools and converts results back into history."""

    def __init__(
        self,
        registry: ToolRegistry,
        hooks: AgentHooks,
        permission_policy: ToolPermissionPolicy | None = None,
    ):
        self.registry = registry
        self.hooks = hooks
        self.permission_policy = permission_policy or AllowAllToolPermissionPolicy()

    async def execute(self, calls: Iterable[ToolCall]) -> ToolExecutionBatch:
        call_list = list(calls)
        allowed_calls: List[ToolCall] = []
        allowed_indexes: List[int] = []
        results_by_index: dict[int, ToolResult] = {}

        decisions = await asyncio.gather(*(self.permission_policy.authorize(call) for call in call_list))
        for index, (call, decision) in enumerate(zip(call_list, decisions)):
            if decision.allowed:
                allowed_indexes.append(index)
                allowed_calls.append(call)
            else:
                results_by_index[index] = _denied_result(call, decision)

        if allowed_calls:
            allowed_results = await self.registry.execute_many(allowed_calls)
            for index, result in zip(allowed_indexes, allowed_results):
                results_by_index[index] = result

        results = [results_by_index[index] for index in range(len(call_list))]
        return ToolExecutionBatch(
            results=results,
            events=[tool_result_event(result) for result in results],
            messages=[self.hooks.format_tool_result(result) for result in results],
        )


def _denied_result(call: ToolCall, decision: ToolPermissionDecision) -> ToolResult:
    reason = decision.reason or "tool call denied by permission policy"
    return ToolResult(
        tool_call_id=call.id,
        name=call.name,
        content=reason,
        is_error=True,
        raw={"permission": decision.to_dict(), "tool_call": call.to_dict()},
    )
