from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class ToolExecutionScope:
    run_id: str = ""
    task_id: str = ""
    tool_call_id: str = ""
    tool_name: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "run_id": self.run_id,
            "task_id": self.task_id,
            "tool_call_id": self.tool_call_id,
            "tool_name": self.tool_name,
        }


class ToolExecutionObserver(Protocol):
    async def before_tool(self, scope: ToolExecutionScope, arguments: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError()

    async def after_tool(
        self,
        scope: ToolExecutionScope,
        arguments: dict[str, Any],
        *,
        result: Any = None,
        is_error: bool = False,
        error: str = "",
        duration_ms: float = 0.0,
    ) -> dict[str, Any]:
        raise NotImplementedError()
