from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, List, Optional, Protocol
from uuid import uuid4

from agent.specs import AgentSpec
from agent.schema import RuntimeEvent


class RunStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    AWAITING_APPROVAL = "awaiting_approval"
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
    spec: dict[str, Any] = field(default_factory=dict)

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
            spec=resolved.to_dict(include_secrets=False),
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
            "spec": dict(self.spec),
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
            events=[event_from_dict(event) for event in payload.get("events", [])],
            created_at=float(payload.get("created_at", time.time())),
            updated_at=float(payload.get("updated_at", time.time())),
            metadata={key: str(value) for key, value in dict(payload.get("metadata", {})).items()},
            spec=dict(payload.get("spec", {})),
        )

    def to_agent_spec(self) -> AgentSpec:
        return AgentSpec.from_dict(self.spec)


class RunStore(Protocol):
    async def create_run(self, spec: AgentSpec, run_id: str = "") -> RunRecord:
        raise NotImplementedError()

    async def load_run(self, run_id: str) -> Optional[RunRecord]:
        raise NotImplementedError()

    async def append_event(self, run_id: str, event: RuntimeEvent) -> Optional[RunRecord]:
        raise NotImplementedError()

    async def set_status(self, run_id: str, status: RunStatus) -> Optional[RunRecord]:
        raise NotImplementedError()


def event_from_dict(payload: dict) -> RuntimeEvent:
    return RuntimeEvent(
        type=str(payload["type"]),
        name=str(payload.get("name", "")),
        payload=dict(payload.get("payload", {})),
        raw=payload.get("raw"),
    )


def _new_run_id() -> str:
    return "run_%s" % uuid4().hex
