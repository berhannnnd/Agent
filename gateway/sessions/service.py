from __future__ import annotations

from agent.specs import AgentSpec
from agent.state.runs import InMemoryRunStore, RunRecord, RunStatus, RunStore
from agent.schema import RuntimeEvent
from agent.governance.tracing import InMemoryTraceStore, RuntimeTraceRecorder


class GatewayRunService:
    def __init__(self, store: RunStore | None = None, trace_recorder: RuntimeTraceRecorder | None = None):
        self.store = store or InMemoryRunStore()
        self.trace_recorder = trace_recorder or RuntimeTraceRecorder(InMemoryTraceStore())

    async def start(self, spec: AgentSpec) -> RunRecord:
        record = await self.store.create_run(spec)
        record = await self.store.set_status(record.run_id, RunStatus.RUNNING) or record
        await self.trace_recorder.start_run(record)
        await self.record_event(record.run_id, run_created_event(record.run_id))
        return record

    async def record_event(self, run_id: str, event: RuntimeEvent) -> None:
        await self.store.append_event(run_id, event)
        await self.trace_recorder.record_runtime_event(run_id, event)

    async def record_events(self, run_id: str, events: list[RuntimeEvent]) -> None:
        for event in events:
            await self.record_event(run_id, event)

    async def mark_running(self, run_id: str) -> None:
        await self.store.set_status(run_id, RunStatus.RUNNING)
        await self.trace_recorder.mark_run_running(run_id)

    async def pause_for_approval(self, run_id: str) -> None:
        await self.store.set_status(run_id, RunStatus.AWAITING_APPROVAL)
        await self.trace_recorder.mark_run_waiting(run_id)

    async def finish(self, run_id: str, error: str = "") -> None:
        status = RunStatus.ERROR if error else RunStatus.FINISHED
        await self.store.set_status(run_id, status)
        await self.trace_recorder.finish_run(run_id, error=error)


def run_created_event(run_id: str) -> RuntimeEvent:
    return RuntimeEvent(type="run_created", name="run", payload={"run_id": run_id})
