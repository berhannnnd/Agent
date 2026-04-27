from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from app.agent.schema import Message, ModelResponse, ToolResult

if TYPE_CHECKING:
    from app.agent.runtime import AgentResult


class AgentHooks:
    """Agent Runtime 扩展钩子。子类覆盖需要的方法即可。"""

    async def before_request(self, messages: List[Message]) -> List[Message]:
        """在消息发给模型前调用，可修改/增强消息列表。"""
        return messages

    async def after_response(self, response: ModelResponse) -> ModelResponse:
        """在模型返回后调用，可检查/修改响应。"""
        return response

    def format_tool_result(self, result: ToolResult) -> Message:
        """在工具结果加入消息列表前调用，返回格式化后的消息。"""
        return Message.from_text(
            "tool",
            result.content,
            tool_call_id=result.tool_call_id,
            name=result.name,
            raw=result.to_dict(),
        )

    async def on_error(self, error: Exception, messages: List[Message]) -> Optional[AgentResult]:
        """出错时调用，返回恢复结果则覆盖默认错误处理，返回 None 走默认逻辑。"""
        return None
