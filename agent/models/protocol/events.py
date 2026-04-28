from __future__ import annotations

from enum import Enum
from typing import Any

from agent.schema import ModelResponse, ModelStreamEvent, ModelUsage, ToolCall


class ModelStreamEventType(str, Enum):
    TEXT_DELTA = "text_delta"
    REASONING_DELTA = "reasoning_delta"
    TOOL_CALL_DELTA = "tool_call_delta"
    USAGE = "usage"
    RETRY = "retry"
    MESSAGE = "message"


def text_delta(delta: str, raw: Any = None) -> ModelStreamEvent:
    return ModelStreamEvent(type=ModelStreamEventType.TEXT_DELTA.value, delta=delta, raw=raw)


def reasoning_delta(delta: str, raw: Any = None) -> ModelStreamEvent:
    return ModelStreamEvent(type=ModelStreamEventType.REASONING_DELTA.value, delta=delta, raw=raw)


def tool_call_delta(tool_call: ToolCall, raw: Any = None) -> ModelStreamEvent:
    return ModelStreamEvent(type=ModelStreamEventType.TOOL_CALL_DELTA.value, tool_call=tool_call, raw=raw)


def usage_event(usage: ModelUsage, raw: Any = None) -> ModelStreamEvent:
    return ModelStreamEvent(type=ModelStreamEventType.USAGE.value, usage=usage, raw=raw)


def retry_event(raw: Any = None) -> ModelStreamEvent:
    return ModelStreamEvent(type=ModelStreamEventType.RETRY.value, raw=raw)


def message_event(response: ModelResponse, raw: Any = None) -> ModelStreamEvent:
    return ModelStreamEvent(type=ModelStreamEventType.MESSAGE.value, response=response, raw=raw)
