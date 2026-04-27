from __future__ import annotations

from agent.schema import ModelResponse, RuntimeEvent, ToolCall, ToolResult
from agent.security.permissions import ToolPermissionDecision


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


def tool_approval_required_event(call: ToolCall, decision: ToolPermissionDecision) -> RuntimeEvent:
    return RuntimeEvent(
        type="tool_approval_required",
        name=call.name,
        payload={
            "approval_id": tool_approval_id(call),
            "tool_call": call.to_dict(),
            "permission": decision.to_dict(),
        },
    )


def tool_approval_decision_event(call: ToolCall, approved: bool, reason: str = "") -> RuntimeEvent:
    payload = {
        "approval_id": tool_approval_id(call),
        "tool_call": call.to_dict(),
        "approved": approved,
    }
    if reason:
        payload["reason"] = reason
    return RuntimeEvent(type="tool_approval_decision", name=call.name, payload=payload)


def tool_approval_id(call: ToolCall) -> str:
    return call.id or call.name


def error_event(kind: str, message: str) -> RuntimeEvent:
    return RuntimeEvent(type="error", name=kind, payload={"message": message})
