from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class ToolPermissionSpec:
    mode: str = "auto"
    allowed_tools: Optional[list[str]] = None
    denied_tools: list[str] = field(default_factory=list)
    approval_required_tools: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict | None) -> "ToolPermissionSpec":
        if not payload:
            return cls()
        allowed = payload.get("allowed_tools")
        return cls(
            mode=str(payload.get("mode") or "auto"),
            allowed_tools=list(allowed) if allowed is not None else None,
            denied_tools=list(payload.get("denied_tools") or []),
            approval_required_tools=list(payload.get("approval_required_tools") or []),
        )

    def normalized_mode(self) -> str:
        mode = (self.mode or "auto").strip().lower()
        if mode in {"auto", "ask", "deny"}:
            return mode
        return "auto"

    def to_dict(self) -> dict:
        payload = {
            "mode": self.normalized_mode(),
            "denied_tools": list(self.denied_tools),
            "approval_required_tools": list(self.approval_required_tools),
        }
        if self.allowed_tools is not None:
            payload["allowed_tools"] = list(self.allowed_tools)
        return payload
