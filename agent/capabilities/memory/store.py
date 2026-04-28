from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Dict, List, Optional, Protocol
from uuid import uuid4

from agent.persistence import SQLiteDatabase, json_dict, json_dumps


class MemoryScope(str, Enum):
    USER = "user"
    AGENT = "agent"
    WORKSPACE = "workspace"
    RUN = "run"


@dataclass(frozen=True)
class MemoryRecord:
    memory_id: str
    tenant_id: str
    user_id: str
    content: str
    scope: MemoryScope = MemoryScope.USER
    agent_id: str = ""
    workspace_id: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @classmethod
    def create(
        cls,
        *,
        tenant_id: str,
        user_id: str,
        content: str,
        scope: MemoryScope = MemoryScope.USER,
        agent_id: str = "",
        workspace_id: str = "",
        metadata: dict[str, str] | None = None,
    ) -> "MemoryRecord":
        return cls(
            memory_id="mem_%s" % uuid4().hex,
            tenant_id=tenant_id,
            user_id=user_id,
            agent_id=agent_id,
            workspace_id=workspace_id,
            scope=scope,
            content=content,
            metadata=dict(metadata or {}),
        )

    def with_update(self) -> "MemoryRecord":
        return replace(self, updated_at=time.time())

    def to_dict(self) -> dict:
        return {
            "memory_id": self.memory_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "workspace_id": self.workspace_id,
            "scope": self.scope.value,
            "content": self.content,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class MemoryStore(Protocol):
    async def save(self, memory: MemoryRecord) -> None:
        raise NotImplementedError()

    async def load(self, memory_id: str) -> Optional[MemoryRecord]:
        raise NotImplementedError()

    async def list_for_context(
        self,
        tenant_id: str,
        user_id: str,
        agent_id: str = "",
        workspace_id: str = "",
    ) -> List[MemoryRecord]:
        raise NotImplementedError()

    async def delete(self, memory_id: str) -> None:
        raise NotImplementedError()


class InMemoryMemoryStore:
    def __init__(self):
        self._memories: Dict[str, MemoryRecord] = {}

    async def save(self, memory: MemoryRecord) -> None:
        self._memories[memory.memory_id] = memory.with_update()

    async def load(self, memory_id: str) -> Optional[MemoryRecord]:
        return self._memories.get(memory_id)

    async def list_for_context(
        self,
        tenant_id: str,
        user_id: str,
        agent_id: str = "",
        workspace_id: str = "",
    ) -> List[MemoryRecord]:
        return sorted(
            [
                memory
                for memory in self._memories.values()
                if _memory_matches(memory, tenant_id, user_id, agent_id, workspace_id)
            ],
            key=lambda memory: (memory.created_at, memory.memory_id),
        )

    async def delete(self, memory_id: str) -> None:
        self._memories.pop(memory_id, None)


class SQLiteMemoryStore:
    def __init__(self, database: SQLiteDatabase):
        self.database = database

    async def save(self, memory: MemoryRecord) -> None:
        record = memory.with_update()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO memory_records (
                    memory_id, tenant_id, user_id, agent_id, workspace_id,
                    scope, content, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(memory_id) DO UPDATE SET
                    tenant_id = excluded.tenant_id,
                    user_id = excluded.user_id,
                    agent_id = excluded.agent_id,
                    workspace_id = excluded.workspace_id,
                    scope = excluded.scope,
                    content = excluded.content,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    record.memory_id,
                    record.tenant_id,
                    record.user_id,
                    record.agent_id,
                    record.workspace_id,
                    record.scope.value,
                    record.content,
                    json_dumps(record.metadata),
                    record.created_at,
                    record.updated_at,
                ),
            )

    async def load(self, memory_id: str) -> Optional[MemoryRecord]:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM memory_records WHERE memory_id = ?", (memory_id,)).fetchone()
        return _memory_from_row(row) if row is not None else None

    async def list_for_context(
        self,
        tenant_id: str,
        user_id: str,
        agent_id: str = "",
        workspace_id: str = "",
    ) -> List[MemoryRecord]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM memory_records
                WHERE tenant_id = ?
                  AND user_id = ?
                  AND (agent_id = '' OR agent_id = ?)
                  AND (workspace_id = '' OR workspace_id = ?)
                ORDER BY created_at ASC, memory_id ASC
                """,
                (tenant_id, user_id, agent_id, workspace_id),
            ).fetchall()
        return [_memory_from_row(row) for row in rows]

    async def delete(self, memory_id: str) -> None:
        with self.database.connect() as connection:
            connection.execute("DELETE FROM memory_records WHERE memory_id = ?", (memory_id,))


def _memory_matches(memory: MemoryRecord, tenant_id: str, user_id: str, agent_id: str, workspace_id: str) -> bool:
    return (
        memory.tenant_id == tenant_id
        and memory.user_id == user_id
        and memory.agent_id in ("", agent_id)
        and memory.workspace_id in ("", workspace_id)
    )


def _memory_from_row(row) -> MemoryRecord:
    return MemoryRecord(
        memory_id=str(row["memory_id"]),
        tenant_id=str(row["tenant_id"]),
        user_id=str(row["user_id"]),
        agent_id=str(row["agent_id"] or ""),
        workspace_id=str(row["workspace_id"] or ""),
        scope=MemoryScope(str(row["scope"])),
        content=str(row["content"]),
        metadata={key: str(value) for key, value in json_dict(row["metadata_json"]).items()},
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
    )
