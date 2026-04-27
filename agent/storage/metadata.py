from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Protocol, Tuple

from agent.context.workspace import WorkspaceContext
from agent.persistence import SQLiteDatabase, json_dict, json_dumps


@dataclass(frozen=True)
class WorkspaceRecord:
    tenant_id: str
    user_id: str
    agent_id: str
    workspace_id: str
    path: str
    status: str = "active"
    metadata: dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @classmethod
    def from_context(cls, workspace: WorkspaceContext, status: str = "active") -> "WorkspaceRecord":
        return cls(
            tenant_id=workspace.tenant_id,
            user_id=workspace.user_id,
            agent_id=workspace.agent_id,
            workspace_id=workspace.workspace_id,
            path=str(workspace.path),
            status=status,
        )

    def with_update(self) -> "WorkspaceRecord":
        return replace(self, updated_at=time.time())

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "workspace_id": self.workspace_id,
            "path": self.path,
            "status": self.status,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class WorkspaceStore(Protocol):
    async def save(self, workspace: WorkspaceRecord) -> None:
        raise NotImplementedError()

    async def load(self, tenant_id: str, user_id: str, agent_id: str, workspace_id: str) -> Optional[WorkspaceRecord]:
        raise NotImplementedError()

    async def list_for_agent(self, tenant_id: str, user_id: str, agent_id: str) -> List[WorkspaceRecord]:
        raise NotImplementedError()


class InMemoryWorkspaceStore:
    def __init__(self):
        self._workspaces: Dict[Tuple[str, str, str, str], WorkspaceRecord] = {}

    async def save(self, workspace: WorkspaceRecord) -> None:
        key = (workspace.tenant_id, workspace.user_id, workspace.agent_id, workspace.workspace_id)
        self._workspaces[key] = workspace.with_update()

    async def load(self, tenant_id: str, user_id: str, agent_id: str, workspace_id: str) -> Optional[WorkspaceRecord]:
        return self._workspaces.get((tenant_id, user_id, agent_id, workspace_id))

    async def list_for_agent(self, tenant_id: str, user_id: str, agent_id: str) -> List[WorkspaceRecord]:
        return sorted(
            [
                workspace
                for key, workspace in self._workspaces.items()
                if key[0] == tenant_id and key[1] == user_id and key[2] == agent_id
            ],
            key=lambda workspace: workspace.workspace_id,
        )


class SQLiteWorkspaceStore:
    def __init__(self, database: SQLiteDatabase):
        self.database = database

    async def save(self, workspace: WorkspaceRecord) -> None:
        record = workspace.with_update()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO workspace_records (
                    tenant_id, user_id, agent_id, workspace_id, path, status,
                    metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, user_id, agent_id, workspace_id) DO UPDATE SET
                    path = excluded.path,
                    status = excluded.status,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    record.tenant_id,
                    record.user_id,
                    record.agent_id,
                    record.workspace_id,
                    record.path,
                    record.status,
                    json_dumps(record.metadata),
                    record.created_at,
                    record.updated_at,
                ),
            )

    async def load(self, tenant_id: str, user_id: str, agent_id: str, workspace_id: str) -> Optional[WorkspaceRecord]:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM workspace_records
                WHERE tenant_id = ? AND user_id = ? AND agent_id = ? AND workspace_id = ?
                """,
                (tenant_id, user_id, agent_id, workspace_id),
            ).fetchone()
        return _workspace_from_row(row) if row is not None else None

    async def list_for_agent(self, tenant_id: str, user_id: str, agent_id: str) -> List[WorkspaceRecord]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM workspace_records
                WHERE tenant_id = ? AND user_id = ? AND agent_id = ?
                ORDER BY workspace_id ASC
                """,
                (tenant_id, user_id, agent_id),
            ).fetchall()
        return [_workspace_from_row(row) for row in rows]


def _workspace_from_row(row) -> WorkspaceRecord:
    return WorkspaceRecord(
        tenant_id=str(row["tenant_id"]),
        user_id=str(row["user_id"]),
        agent_id=str(row["agent_id"]),
        workspace_id=str(row["workspace_id"]),
        path=str(row["path"]),
        status=str(row["status"] or "active"),
        metadata={key: str(value) for key, value in json_dict(row["metadata_json"]).items()},
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
    )
