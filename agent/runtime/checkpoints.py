from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol

from agent.persistence import SQLiteDatabase
from agent.runtime.state import RuntimeState
from agent.schema import Message, RuntimeEvent, ToolCall, ToolResult


@dataclass(frozen=True)
class RuntimeCheckpoint:
    run_id: str
    step: str
    iteration: int
    messages: List[Message]
    tool_results: List[ToolResult] = field(default_factory=list)
    events: List[RuntimeEvent] = field(default_factory=list)
    pending_tool_calls: List[ToolCall] = field(default_factory=list)
    tool_approvals: Dict[str, bool] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    @classmethod
    def from_state(cls, run_id: str, step: str, state: RuntimeState) -> "RuntimeCheckpoint":
        return cls(
            run_id=run_id,
            step=step,
            iteration=state.iteration,
            messages=list(state.messages),
            tool_results=list(state.tool_results),
            events=list(state.events),
            pending_tool_calls=list(state.pending_tool_calls),
            tool_approvals=dict(state.tool_approvals),
        )

    def to_state(self) -> RuntimeState:
        return RuntimeState(
            messages=list(self.messages),
            tool_results=list(self.tool_results),
            events=list(self.events),
            iteration=self.iteration,
            pending_tool_calls=list(self.pending_tool_calls),
            tool_approvals=dict(self.tool_approvals),
        )


class CheckpointStore(Protocol):
    async def save(self, checkpoint: RuntimeCheckpoint) -> None:
        raise NotImplementedError()

    async def load(self, run_id: str) -> Optional[RuntimeCheckpoint]:
        raise NotImplementedError()

    async def clear(self, run_id: str) -> None:
        raise NotImplementedError()


class NullCheckpointStore:
    async def save(self, checkpoint: RuntimeCheckpoint) -> None:
        return None

    async def load(self, run_id: str) -> Optional[RuntimeCheckpoint]:
        return None

    async def clear(self, run_id: str) -> None:
        return None


class InMemoryCheckpointStore:
    def __init__(self):
        self._checkpoints: Dict[str, RuntimeCheckpoint] = {}

    async def save(self, checkpoint: RuntimeCheckpoint) -> None:
        self._checkpoints[checkpoint.run_id] = checkpoint

    async def load(self, run_id: str) -> Optional[RuntimeCheckpoint]:
        return self._checkpoints.get(run_id)

    async def clear(self, run_id: str) -> None:
        self._checkpoints.pop(run_id, None)


class SQLiteCheckpointStore:
    def __init__(self, database: SQLiteDatabase):
        self.database = database

    async def save(self, checkpoint: RuntimeCheckpoint) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO runtime_checkpoints (
                    run_id, step, iteration, messages_json, tool_results_json, events_json,
                    pending_tool_calls_json, tool_approvals_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id) DO UPDATE SET
                    step = excluded.step,
                    iteration = excluded.iteration,
                    messages_json = excluded.messages_json,
                    tool_results_json = excluded.tool_results_json,
                    events_json = excluded.events_json,
                    pending_tool_calls_json = excluded.pending_tool_calls_json,
                    tool_approvals_json = excluded.tool_approvals_json,
                    created_at = excluded.created_at
                """,
                (
                    checkpoint.run_id,
                    checkpoint.step,
                    checkpoint.iteration,
                    _json_dumps([message.to_dict() for message in checkpoint.messages]),
                    _json_dumps([result.to_dict() for result in checkpoint.tool_results]),
                    _json_dumps([event.to_dict() for event in checkpoint.events]),
                    _json_dumps([call.to_dict() for call in checkpoint.pending_tool_calls]),
                    _json_dumps(checkpoint.tool_approvals),
                    checkpoint.created_at,
                ),
            )

    async def load(self, run_id: str) -> Optional[RuntimeCheckpoint]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM runtime_checkpoints WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        if row is None:
            return None
        return RuntimeCheckpoint(
            run_id=str(row["run_id"]),
            step=str(row["step"]),
            iteration=int(row["iteration"]),
            messages=[Message.from_dict(item) for item in json.loads(row["messages_json"] or "[]")],
            tool_results=[ToolResult.from_dict(item) for item in json.loads(row["tool_results_json"] or "[]")],
            events=[_event_from_dict(item) for item in json.loads(row["events_json"] or "[]")],
            pending_tool_calls=[ToolCall.from_dict(item) for item in json.loads(row["pending_tool_calls_json"] or "[]")],
            tool_approvals={str(key): bool(value) for key, value in json.loads(row["tool_approvals_json"] or "{}").items()},
            created_at=float(row["created_at"]),
        )

    async def clear(self, run_id: str) -> None:
        with self.database.connect() as connection:
            connection.execute("DELETE FROM runtime_checkpoints WHERE run_id = ?", (run_id,))


def _event_from_dict(payload: dict) -> RuntimeEvent:
    return RuntimeEvent(
        type=str(payload["type"]),
        name=str(payload.get("name", "")),
        payload=dict(payload.get("payload", {})),
        raw=payload.get("raw"),
    )


def _json_dumps(value) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)
