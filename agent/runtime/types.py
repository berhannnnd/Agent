from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncIterable, List, Protocol

from agent.schema import Message, ModelRequest, ModelResponse, ModelStreamEvent, RuntimeEvent, ToolResult


class ModelClientProtocol(Protocol):
    async def async_complete(self, request_data: ModelRequest) -> ModelResponse:
        raise NotImplementedError()

    async def async_stream(self, request_data: ModelRequest) -> AsyncIterable[ModelStreamEvent]:
        raise NotImplementedError()


@dataclass
class AgentResult:
    content: str
    messages: List[Message]
    tool_results: List[ToolResult] = field(default_factory=list)
    events: List[RuntimeEvent] = field(default_factory=list)
    status: str = "finished"
