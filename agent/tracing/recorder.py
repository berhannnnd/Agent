from __future__ import annotations

from agent.runs import RunRecord
from agent.schema import RuntimeEvent
from agent.tracing.types import TraceSpan, TraceStatus, TraceStore


class RuntimeTraceRecorder:
    def __init__(self, store: TraceStore):
        self.store = store

    async def start_run(self, record: RunRecord) -> None:
        await self.store.save_span(
            TraceSpan.start(
                run_id=record.run_id,
                span_id=_run_span_id(record.run_id),
                kind="run",
                name="agent.run",
                attributes={
                    "agent_id": record.agent_id,
                    "tenant_id": record.tenant_id,
                    "user_id": record.user_id,
                    "workspace_id": record.workspace_id,
                },
            )
        )

    async def mark_run_waiting(self, run_id: str) -> None:
        await self._mark_or_create_run_span(run_id, TraceStatus.WAITING)

    async def mark_run_running(self, run_id: str) -> None:
        await self._mark_or_create_run_span(run_id, TraceStatus.RUNNING)

    async def finish_run(self, run_id: str, error: str = "") -> None:
        status = TraceStatus.ERROR if error else TraceStatus.DONE
        await self._finish_or_create_run_span(run_id, status, error=error)

    async def record_runtime_event(self, run_id: str, event: RuntimeEvent) -> None:
        if event.type == "tool_start":
            await self._start_tool(run_id, event)
            return
        if event.type == "tool_result":
            await self._finish_tool(run_id, event)
            return
        if event.type == "tool_approval_required":
            await self._start_approval(run_id, event)
            return
        if event.type == "tool_approval_decision":
            await self._finish_approval(run_id, event)
            return
        if event.type == "model_message":
            await self._instant(run_id, "model", event.name or "assistant", TraceStatus.DONE, event.payload)
            return
        if event.type == "error":
            await self._instant(run_id, "error", event.name or "runtime", TraceStatus.ERROR, event.payload)

    async def _start_tool(self, run_id: str, event: RuntimeEvent) -> None:
        call = event.payload or {}
        await self.store.save_span(
            TraceSpan.start(
                run_id=run_id,
                span_id=_tool_span_id(run_id, str(call.get("id") or event.name)),
                parent_span_id=_run_span_id(run_id),
                kind="tool",
                name=event.name or str(call.get("name") or "tool"),
                attributes={"tool_call": call},
            )
        )

    async def _finish_tool(self, run_id: str, event: RuntimeEvent) -> None:
        payload = event.payload or {}
        tool_call_id = str(payload.get("tool_call_id") or event.name)
        span_id = _tool_span_id(run_id, tool_call_id)
        span = await self.store.load_span(span_id)
        if span is None:
            span = TraceSpan.start(
                run_id=run_id,
                span_id=span_id,
                parent_span_id=_run_span_id(run_id),
                kind="tool",
                name=event.name or "tool",
            )
        status = TraceStatus.ERROR if payload.get("is_error") else TraceStatus.DONE
        await self.store.save_span(span.finish(status=status, attributes={"tool_result": payload}))

    async def _start_approval(self, run_id: str, event: RuntimeEvent) -> None:
        approval_id = str(event.payload.get("approval_id") or event.name)
        await self.store.save_span(
            TraceSpan.start(
                run_id=run_id,
                span_id=_approval_span_id(run_id, approval_id),
                parent_span_id=_run_span_id(run_id),
                kind="approval",
                name=event.name or "tool_approval",
                status=TraceStatus.WAITING,
                attributes=dict(event.payload),
            )
        )

    async def _finish_approval(self, run_id: str, event: RuntimeEvent) -> None:
        payload = event.payload or {}
        approval_id = str(payload.get("approval_id") or event.name)
        span_id = _approval_span_id(run_id, approval_id)
        span = await self.store.load_span(span_id)
        if span is None:
            span = TraceSpan.start(
                run_id=run_id,
                span_id=span_id,
                parent_span_id=_run_span_id(run_id),
                kind="approval",
                name=event.name or "tool_approval",
            )
        status = TraceStatus.DONE if payload.get("approved") else TraceStatus.CANCELED
        await self.store.save_span(span.finish(status=status, attributes={"decision": payload}))

    async def _instant(self, run_id: str, kind: str, name: str, status: TraceStatus, attributes: dict) -> None:
        span = TraceSpan.start(
            run_id=run_id,
            parent_span_id=_run_span_id(run_id),
            kind=kind,
            name=name,
            attributes=dict(attributes or {}),
        )
        error = str(attributes.get("message") or "") if attributes else ""
        await self.store.save_span(span.finish(status=status, error=error))

    async def _finish_or_create_run_span(self, run_id: str, status: TraceStatus, error: str = "") -> None:
        span_id = _run_span_id(run_id)
        span = await self.store.load_span(span_id)
        if span is None:
            span = TraceSpan.start(run_id=run_id, span_id=span_id, kind="run", name="agent.run")
        await self.store.save_span(span.finish(status=status, error=error))

    async def _mark_or_create_run_span(self, run_id: str, status: TraceStatus, error: str = "") -> None:
        span_id = _run_span_id(run_id)
        span = await self.store.load_span(span_id)
        if span is None:
            span = TraceSpan.start(run_id=run_id, span_id=span_id, kind="run", name="agent.run")
        await self.store.save_span(span.with_status(status=status, error=error))


def _run_span_id(run_id: str) -> str:
    return "%s:run" % run_id


def _tool_span_id(run_id: str, tool_call_id: str) -> str:
    return "%s:tool:%s" % (run_id, tool_call_id)


def _approval_span_id(run_id: str, approval_id: str) -> str:
    return "%s:approval:%s" % (run_id, approval_id)
