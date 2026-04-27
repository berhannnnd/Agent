from __future__ import annotations

from typing import Dict, Optional

from agent.definitions import AgentSpec
from agent.runs.types import RunRecord, RunStatus
from agent.schema import RuntimeEvent


class InMemoryRunStore:
    def __init__(self):
        self._runs: Dict[str, RunRecord] = {}

    async def create_run(self, spec: AgentSpec, run_id: str = "") -> RunRecord:
        record = RunRecord.from_spec(spec, run_id=run_id)
        self._runs[record.run_id] = record
        return record

    async def load_run(self, run_id: str) -> Optional[RunRecord]:
        return self._runs.get(run_id)

    async def append_event(self, run_id: str, event: RuntimeEvent) -> Optional[RunRecord]:
        record = self._runs.get(run_id)
        if record is None:
            return None
        updated = record.with_event(event)
        self._runs[run_id] = updated
        return updated

    async def set_status(self, run_id: str, status: RunStatus) -> Optional[RunRecord]:
        record = self._runs.get(run_id)
        if record is None:
            return None
        updated = record.with_status(status)
        self._runs[run_id] = updated
        return updated
