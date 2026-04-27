from __future__ import annotations

from typing import Callable, Optional

from agent.hooks.base import AgentHooks
from agent.schema import ModelResponse


class ThinkingHooks(AgentHooks):
    """提取并处理模型 reasoning/thinking 内容的 Hook。

    某些模型（如 Claude extended thinking、DeepSeek R1）在 raw 响应中
    包含 reasoning_content。此 Hook 将 thinking 内容提取为独立的
    RuntimeEvent，方便上层展示。
    """

    def __init__(
        self,
        extractor: Optional[Callable[[ModelResponse], str]] = None,
        on_thinking: Optional[Callable[[str], None]] = None,
    ):
        self.extractor = extractor or self._default_extractor
        self.on_thinking = on_thinking

    async def after_response(self, response: ModelResponse) -> ModelResponse:
        thinking = self.extractor(response)
        if thinking and self.on_thinking:
            self.on_thinking(thinking)
        return response

    @staticmethod
    def _default_extractor(response: ModelResponse) -> str:
        """从常见字段中提取 reasoning 内容。"""
        raw = response.raw or {}
        if isinstance(raw, dict):
            for key in ("reasoning_content", "thinking", "thought"):
                value = raw.get(key)
                if value:
                    return str(value)
        return ""
