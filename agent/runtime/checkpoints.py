from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Protocol

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
        )

    def to_state(self) -> RuntimeState:
        return RuntimeState(
            messages=list(self.messages),
            tool_results=list(self.tool_results),
            events=list(self.events),
            iteration=self.iteration,
            pending_tool_calls=list(self.pending_tool_calls),
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
