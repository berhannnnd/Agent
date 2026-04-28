from __future__ import annotations

import json
from typing import Any

from agent.capabilities.sandbox.store import SandboxEventRecord, SandboxLeaseRecord, SandboxStore
from agent.capabilities.tools.context import ToolRuntimeContext
from agent.capabilities.tools.recording import ToolExecutionScope


class SandboxToolExecutionRecorder:
    def __init__(self, context: ToolRuntimeContext, store: SandboxStore | None = None):
        self.context = context
        self.store = store

    async def before_tool(self, scope: ToolExecutionScope, arguments: dict[str, Any]) -> dict[str, Any]:
        client = await self.context.bind_execution_scope(scope.run_id, scope.task_id)
        lease = SandboxLeaseRecord.from_lease(client.lease)
        if self.store is not None:
            await self.store.save_lease(lease)
            await self.store.record_event(
                SandboxEventRecord(
                    lease_id=lease.lease_id,
                    event_type="tool_started",
                    run_id=scope.run_id,
                    task_id=scope.task_id or lease.task_id,
                    tool_call_id=scope.tool_call_id,
                    tool_name=scope.tool_name,
                    status="running",
                    payload={"arguments": _compact_json(arguments)},
                )
            )
        return {"sandbox": _sandbox_metadata(lease)}

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
        client = await self.context.bind_execution_scope(scope.run_id, scope.task_id)
        lease = SandboxLeaseRecord.from_lease(client.lease)
        status = "error" if is_error else "succeeded"
        if self.store is not None:
            await self.store.save_lease(lease)
            await self.store.record_event(
                SandboxEventRecord(
                    lease_id=lease.lease_id,
                    event_type="tool_finished",
                    run_id=scope.run_id,
                    task_id=scope.task_id or lease.task_id,
                    tool_call_id=scope.tool_call_id,
                    tool_name=scope.tool_name,
                    status=status,
                    duration_ms=duration_ms,
                    payload={
                        "arguments": _compact_json(arguments),
                        "error": error,
                        "result": _compact_json(result),
                    },
                )
            )
        metadata = _sandbox_metadata(lease)
        metadata.update({"status": status, "duration_ms": duration_ms})
        if error:
            metadata["error"] = error
        return {"sandbox": metadata}


def _sandbox_metadata(lease: SandboxLeaseRecord) -> dict[str, Any]:
    payload = {
        "lease_id": lease.lease_id,
        "provider": lease.provider,
        "run_id": lease.run_id,
        "task_id": lease.task_id,
        "workspace_id": lease.workspace_id,
    }
    return {key: value for key, value in payload.items() if value}


def _compact_json(value: Any, limit: int = 4000) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except TypeError:
        text = str(value)
    if len(text) <= limit:
        return text
    return text[:limit] + "...[truncated]"
