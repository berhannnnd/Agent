from __future__ import annotations

from agent.schema import ModelResponse, RuntimeEvent, ToolResult


def model_message_event(response: ModelResponse) -> RuntimeEvent:
    return RuntimeEvent(
        type="model_message",
        name="assistant",
        payload={
            "content": response.content_text(),
            "tool_call_count": len(response.tool_calls),
        },
    )


def tool_start_event(name: str, payload: dict) -> RuntimeEvent:
    return RuntimeEvent(type="tool_start", name=name, payload=payload)


def tool_result_event(result: ToolResult) -> RuntimeEvent:
    return RuntimeEvent(type="tool_result", name=result.name, payload=result.to_dict())


def error_event(kind: str, message: str) -> RuntimeEvent:
    return RuntimeEvent(type="error", name=kind, payload={"message": message})
