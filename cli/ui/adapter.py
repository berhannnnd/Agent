from __future__ import annotations

from typing import Any

from agent.schema import RuntimeEvent
from cli.ui.activity import tool_activity_id
from cli.ui.events import UIEvent


class RuntimeEventAdapter:
    """Translate SDK runtime events into renderer-neutral CLI UI events."""

    def adapt(self, event: RuntimeEvent) -> UIEvent | None:
        payload = dict(event.payload or {})
        if event.type == "text_delta":
            return UIEvent(type="assistant_delta", name=event.name, text=str(payload.get("delta", "")), payload=payload)
        if event.type == "reasoning_delta":
            return UIEvent(type="thinking_delta", name=event.name, text=str(payload.get("delta", "")), payload=payload)
        if event.type == "model_message":
            return UIEvent(type="assistant_message", name=event.name or "assistant", text=str(payload.get("content", "")), payload=payload)
        if event.type == "tool_start":
            arguments = _tool_arguments(payload)
            impact = _impact(payload)
            tool_id = tool_activity_id(event.name, payload)
            return UIEvent(
                type="tool_started",
                name=event.name,
                payload={
                    **payload,
                    "id": tool_id,
                    "arguments": arguments,
                    "risk": impact.get("risk", "unknown"),
                },
            )
        if event.type == "tool_result":
            return UIEvent(
                type="tool_finished",
                name=event.name,
                text=str(payload.get("content", "")),
                payload={
                    **payload,
                    "id": tool_activity_id(event.name, payload),
                    "is_error": bool(payload.get("is_error")),
                },
            )
        if event.type == "tool_approval_required":
            call = payload.get("tool_call") or {}
            impact = _impact(payload)
            tool_name = str(call.get("name") or event.name)
            return UIEvent(
                type="approval_required",
                name=tool_name,
                payload={
                    **payload,
                    "arguments": _tool_arguments(call),
                    "risk": impact.get("risk", "unknown"),
                },
            )
        if event.type == "tool_approval_decision":
            return UIEvent(type="approval_decision", name=event.name, status=str(payload.get("scope", "")), payload=payload)
        if event.type == "model_retry":
            return UIEvent(type="model_retry", name=event.name or "model", payload=payload)
        if event.type == "error":
            return UIEvent(type="error", name=event.name, text=str(payload.get("message", "runtime error")), payload=payload)
        if event.type == "done":
            return UIEvent(
                type="done",
                name=event.name,
                text=str(payload.get("content", "")),
                status=str(payload.get("status") or "finished"),
                payload=payload,
            )
        return UIEvent(type="unknown", name=event.name, payload=payload)


def _tool_arguments(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("arguments") or {}
    return dict(value) if isinstance(value, dict) else {}


def _impact(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("impact") or {}
    return dict(value) if isinstance(value, dict) else {}
