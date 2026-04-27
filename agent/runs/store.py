from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
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

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "agent_id": self.agent_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "workspace_id": self.workspace_id,
            "status": self.status.value,
            "events": [event.to_dict() for event in self.events],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, payload: dict) -> "RunRecord":
        return cls(
            run_id=str(payload["run_id"]),
            agent_id=str(payload.get("agent_id", "")),
            tenant_id=str(payload.get("tenant_id", "")),
            user_id=str(payload.get("user_id", "")),
            workspace_id=str(payload.get("workspace_id", "")),
            status=RunStatus(payload.get("status", RunStatus.CREATED.value)),
            events=[_event_from_dict(event) for event in payload.get("events", [])],
            created_at=float(payload.get("created_at", time.time())),
            updated_at=float(payload.get("updated_at", time.time())),
            metadata={key: str(value) for key, value in dict(payload.get("metadata", {})).items()},
        )


class RunStore(Protocol):
    async def create_run(self, spec: AgentSpec, run_id: str = "") -> RunRecord:
        raise NotImplementedError()

    async def load_run(self, run_id: str) -> Optional[RunRecord]:
        raise NotImplementedError()

    async def append_event(self, run_id: str, event: RuntimeEvent) -> Optional[RunRecord]:
        raise NotImplementedError()

    async def set_status(self, run_id: str, status: RunStatus) -> Optional[RunRecord]:
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

    async def set_status(self, run_id: str, status: RunStatus) -> Optional[RunRecord]:
        record = self._runs.get(run_id)
        if record is None:
            return None
        updated = record.with_status(status)
        self._runs[run_id] = updated
        return updated


class LocalFileRunStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    async def create_run(self, spec: AgentSpec, run_id: str = "") -> RunRecord:
        record = RunRecord.from_spec(spec, run_id=run_id)
        self._write(record)
        return record

    async def load_run(self, run_id: str) -> Optional[RunRecord]:
        path = self._path(run_id)
        if not path.exists():
            return None
        return RunRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))

    async def append_event(self, run_id: str, event: RuntimeEvent) -> Optional[RunRecord]:
        record = await self.load_run(run_id)
        if record is None:
            return None
        updated = record.with_event(event)
        self._write(updated)
        return updated

    async def set_status(self, run_id: str, status: RunStatus) -> Optional[RunRecord]:
        record = await self.load_run(run_id)
        if record is None:
            return None
        updated = record.with_status(status)
        self._write(updated)
        return updated

    def _path(self, run_id: str) -> Path:
        safe = "".join(ch for ch in run_id if ch.isalnum() or ch in ("_", "-", ".")).strip(".")
        return self.root / ("%s.json" % (safe or "run"))

    def _write(self, record: RunRecord) -> None:
        path = self._path(record.run_id)
        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(path)


def _new_run_id() -> str:
    return "run_%s" % uuid4().hex


def _event_from_dict(payload: dict) -> RuntimeEvent:
    return RuntimeEvent(
        type=str(payload["type"]),
        name=str(payload.get("name", "")),
        payload=dict(payload.get("payload", {})),
        raw=payload.get("raw"),
    )
