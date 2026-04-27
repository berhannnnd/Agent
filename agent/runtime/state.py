from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from agent.schema import Message, RuntimeEvent, ToolCall, ToolResult


@dataclass
class RuntimeState:
    messages: List[Message]
    tool_results: List[ToolResult] = field(default_factory=list)
    events: List[RuntimeEvent] = field(default_factory=list)
    iteration: int = 0
    pending_tool_calls: List[ToolCall] = field(default_factory=list)

    @classmethod
    def from_messages(cls, messages: List[Message]) -> "RuntimeState":
        return cls(messages=list(messages))
