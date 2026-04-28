from __future__ import annotations

import json
from typing import Any

from agent.capabilities.sandbox.store import (
    SandboxEventRecord,
    SandboxLeaseRecord,
    SandboxStore,
    SandboxWorkspaceSnapshotRecord,
)
from agent.capabilities.sandbox.workspace import WorkspaceSnapshot
from agent.capabilities.tools.context import ToolRuntimeContext
from agent.capabilities.tools.recording import ToolExecutionScope


class SandboxToolExecutionRecorder:
    def __init__(self, context: ToolRuntimeContext, store: SandboxStore | None = None):
        self.context = context
        self.store = store
        self._before_snapshots: dict[str, WorkspaceSnapshot] = {}
        self._snapshot_counts: dict[str, int] = {}

    async def before_tool(self, scope: ToolExecutionScope, arguments: dict[str, Any]) -> dict[str, Any]:
        client = await self.context.bind_execution_scope(scope.run_id, scope.task_id)
        lease = SandboxLeaseRecord.from_lease(client.lease)
        if self.store is not None:
            await self.store.save_lease(lease)
            await self._record_before_snapshot(lease)
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
            await self._record_after_snapshot(lease)
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

    async def _record_before_snapshot(self, lease: SandboxLeaseRecord) -> None:
        if lease.lease_id in self._before_snapshots or self.store is None:
            return
        snapshot = WorkspaceSnapshot.capture(self.context.workspace)
        self._before_snapshots[lease.lease_id] = snapshot
        await self.store.save_workspace_snapshot(
            _snapshot_record(
                lease,
                phase="before",
                snapshot=snapshot,
                diff={},
                sequence=0,
            )
        )

    async def _record_after_snapshot(self, lease: SandboxLeaseRecord) -> None:
        if self.store is None:
            return
        before = self._before_snapshots.get(lease.lease_id)
        after = WorkspaceSnapshot.capture(self.context.workspace)
        count = self._snapshot_counts.get(lease.lease_id, 0) + 1
        self._snapshot_counts[lease.lease_id] = count
        diff = before.diff(after) if before is not None else {}
        await self.store.save_workspace_snapshot(
            _snapshot_record(
                lease,
                phase="after",
                snapshot=after,
                diff=diff,
                sequence=count,
            )
        )


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


def _snapshot_record(
    lease: SandboxLeaseRecord,
    *,
    phase: str,
    snapshot: WorkspaceSnapshot,
    diff: dict[str, Any],
    sequence: int,
) -> SandboxWorkspaceSnapshotRecord:
    return SandboxWorkspaceSnapshotRecord(
        snapshot_id="%s:%s:%04d" % (lease.lease_id, phase, sequence),
        lease_id=lease.lease_id,
        run_id=lease.run_id,
        task_id=lease.task_id,
        phase=phase,
        file_count=len(snapshot.files),
        total_bytes=sum(item.size for item in snapshot.files.values()),
        manifest=snapshot.to_dict(),
        diff=diff,
        created_at=snapshot.captured_at,
    )
