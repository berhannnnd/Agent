from __future__ import annotations

from typing import List

from agent.runtime.context import RuntimeConfig
from agent.schema import Message, ModelRequest
from agent.tools.registry import ToolRegistry


class PromptCompiler:
    """Builds provider-neutral model requests from runtime state."""

    def __init__(self, tools: ToolRegistry):
        self.tools = tools

    def compile(self, messages: List[Message], config: RuntimeConfig) -> ModelRequest:
        return ModelRequest(
            provider=config.provider,
            model=config.model,
            messages=list(messages),
            tools=self.tools.specs(config.tool_names()),
        )
