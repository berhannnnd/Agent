from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol
from uuid import uuid4


class TraceStatus(str, Enum):
    RUNNING = "running"
    WAITING = "waiting"
    DONE = "done"
    ERROR = "error"
    CANCELED = "canceled"


@dataclass(frozen=True)
class TraceSpan:
    span_id: str
    run_id: str
    kind: str
    name: str
    parent_span_id: str = ""
    status: TraceStatus = TraceStatus.RUNNING
    started_at: float = field(default_factory=time.time)
    ended_at: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    error: str = ""

    @classmethod
    def start(
        cls,
        *,
        run_id: str,
        kind: str,
        name: str,
        span_id: str = "",
        parent_span_id: str = "",
        attributes: Dict[str, Any] | None = None,
        status: TraceStatus = TraceStatus.RUNNING,
    ) -> "TraceSpan":
        return cls(
            span_id=span_id or new_span_id(),
            run_id=run_id,
            kind=kind,
            name=name,
            parent_span_id=parent_span_id,
            status=status,
            attributes=dict(attributes or {}),
        )

    def finish(
        self,
        status: TraceStatus = TraceStatus.DONE,
        error: str = "",
        attributes: Dict[str, Any] | None = None,
    ) -> "TraceSpan":
        merged = dict(self.attributes)
        merged.update(attributes or {})
        return replace(self, status=status, ended_at=time.time(), error=error, attributes=merged)

    def with_status(
        self,
        status: TraceStatus,
        error: str = "",
        attributes: Dict[str, Any] | None = None,
    ) -> "TraceSpan":
        merged = dict(self.attributes)
        merged.update(attributes or {})
        return replace(self, status=status, error=error or self.error, attributes=merged)

    def to_dict(self) -> dict:
        return {
            "span_id": self.span_id,
            "run_id": self.run_id,
            "parent_span_id": self.parent_span_id,
            "kind": self.kind,
            "name": self.name,
            "status": self.status.value,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "attributes": dict(self.attributes),
            "error": self.error,
        }


class TraceStore(Protocol):
    async def save_span(self, span: TraceSpan) -> None:
        raise NotImplementedError()

    async def load_span(self, span_id: str) -> Optional[TraceSpan]:
        raise NotImplementedError()

    async def list_for_run(self, run_id: str) -> List[TraceSpan]:
        raise NotImplementedError()


def new_span_id() -> str:
    return "span_%s" % uuid4().hex
