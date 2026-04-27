from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Dict, List, Optional, Protocol
from uuid import uuid4

from agent.definitions import AgentSpec
from agent.schema import RuntimeEvent


class RunStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    FINISHED = "finished"
    ERROR = "error"
    CANCELED = "canceled"


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    agent_id: str = ""
    tenant_id: str = ""
    user_id: str = ""
    workspace_id: str = ""
    status: RunStatus = RunStatus.CREATED
    events: List[RuntimeEvent] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_spec(cls, spec: AgentSpec, run_id: str = "") -> "RunRecord":
        resolved = spec.with_workspace_defaults()
        return cls(
            run_id=run_id or _new_run_id(),
            agent_id=resolved.agent_id or resolved.workspace.agent_id,
            tenant_id=resolved.workspace.tenant_id,
            user_id=resolved.workspace.user_id,
            workspace_id=resolved.workspace.workspace_id,
            metadata={key: str(value) for key, value in resolved.metadata.items()},
        )

    def with_status(self, status: RunStatus) -> "RunRecord":
        return replace(self, status=status, updated_at=time.time())

    def with_event(self, event: RuntimeEvent) -> "RunRecord":
        return replace(self, events=[*self.events, event], updated_at=time.time())


class RunStore(Protocol):
    async def create_run(self, spec: AgentSpec, run_id: str = "") -> RunRecord:
        raise NotImplementedError()

    async def load_run(self, run_id: str) -> Optional[RunRecord]:
        raise NotImplementedError()

    async def append_event(self, run_id: str, event: RuntimeEvent) -> Optional[RunRecord]:
        raise NotImplementedError()

    async def finish_run(self, run_id: str, status: RunStatus) -> Optional[RunRecord]:
        raise NotImplementedError()


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

    async def finish_run(self, run_id: str, status: RunStatus) -> Optional[RunRecord]:
        record = self._runs.get(run_id)
        if record is None:
            return None
        updated = record.with_status(status)
        self._runs[run_id] = updated
        return updated


def _new_run_id() -> str:
    return "run_%s" % uuid4().hex
