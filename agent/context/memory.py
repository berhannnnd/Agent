from __future__ import annotations

from dataclasses import dataclass
from typing import List

from agent.capabilities.memory import MemoryRecord, MemoryStore
from agent.context.pack import ContextFragment, ContextLayer, ContextScope


@dataclass(frozen=True)
class MemoryRetrievalScope:
    tenant_id: str
    user_id: str
    agent_id: str = ""
    workspace_id: str = ""
    limit: int = 20


class MemoryContextRetriever:
    def __init__(self, store: MemoryStore):
        self.store = store

    async def fragments_for_scope(self, scope: MemoryRetrievalScope) -> List[ContextFragment]:
        records = await self.store.list_for_context(
            tenant_id=scope.tenant_id,
            user_id=scope.user_id,
            agent_id=scope.agent_id,
            workspace_id=scope.workspace_id,
        )
        selected = records[-max(0, scope.limit) :] if scope.limit else []
        return [_fragment_from_memory(record) for record in selected]


def _fragment_from_memory(memory: MemoryRecord) -> ContextFragment:
    return ContextFragment(
        id="memory.%s" % memory.memory_id,
        layer=ContextLayer.MEMORY,
        text=memory.content,
        source="memory:%s" % memory.scope.value,
        priority=_priority(memory),
        scope=ContextScope.SESSION,
        metadata={
            "memory_id": memory.memory_id,
            "scope": memory.scope.value,
            "tenant_id": memory.tenant_id,
            "user_id": memory.user_id,
            "agent_id": memory.agent_id,
            "workspace_id": memory.workspace_id,
        },
    )


def _priority(memory: MemoryRecord) -> int:
    if memory.workspace_id:
        return 75
    if memory.agent_id:
        return 70
    return 65
