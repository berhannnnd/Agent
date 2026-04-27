from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from app.agent.hooks.base import AgentHooks
from app.agent.schema import Message, ModelResponse, ToolResult

if TYPE_CHECKING:
    from app.agent.runtime import AgentResult


class CompositeHooks(AgentHooks):
    """组合多个 Hook 按顺序执行。

    示例::

        hooks = CompositeHooks([
            IntentGuidanceHooks(guides),
            ThinkingHooks(on_thinking=print),
            ApprovalHooks(should_approve),
        ])
    """

    def __init__(self, hooks: List[AgentHooks]):
        self.hooks = list(hooks)

    async def before_request(self, messages: List[Message]) -> List[Message]:
        working = list(messages)
        for hook in self.hooks:
            working = await hook.before_request(working)
        return working

    async def after_response(self, response: ModelResponse) -> ModelResponse:
        working = response
        for hook in self.hooks:
            working = await hook.after_response(working)
        return working

    def format_tool_result(self, result: ToolResult) -> Message:
        if not self.hooks:
            return super().format_tool_result(result)
        # 后面的 hook 可以覆盖前面的格式化行为
        return self.hooks[-1].format_tool_result(result)

    async def on_error(self, error: Exception, messages: List[Message]) -> Optional[AgentResult]:
        for hook in self.hooks:
            recovery = await hook.on_error(error, messages)
            if recovery is not None:
                return recovery
        return None
