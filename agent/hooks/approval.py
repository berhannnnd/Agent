from __future__ import annotations

from typing import Callable

from agent.hooks.base import AgentHooks
from agent.schema import ModelResponse


class ApprovalHooks(AgentHooks):
    """对危险/特定工具调用进行拦截确认的 Hook。

    在模型返回包含需要确认的工具调用时，抛出自定义异常或返回
    恢复结果，由上层处理用户确认后再继续。

    示例::

        def confirm_handler(tool_name: str, arguments: dict) -> bool:
            return tool_name not in ("shell", "exec")

        hooks = ApprovalHooks(confirm_handler)
    """

    def __init__(
        self,
        should_approve: Callable[[str, dict], bool],
        rejection_message: str = "tool call rejected by approval policy",
    ):
        self.should_approve = should_approve
        self.rejection_message = rejection_message

    async def after_response(self, response: ModelResponse) -> ModelResponse:
        for call in response.tool_calls:
            if not self.should_approve(call.name, dict(call.arguments)):
                raise ToolApprovalError(
                    tool_name=call.name,
                    message=self.rejection_message,
                )
        return response


class ToolApprovalError(Exception):
    """工具调用未通过审批策略时抛出。"""

    def __init__(self, tool_name: str, message: str = ""):
        self.tool_name = tool_name
        super().__init__(message or f"tool '{tool_name}' approval denied")
