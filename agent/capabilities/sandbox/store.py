from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Protocol

from agent.context.workspace import WorkspaceContext
from agent.persistence import SQLiteDatabase, json_dict, json_dumps

from .types import SandboxLease, SandboxProfile


@dataclass(frozen=True)
class SandboxLeaseRecord:
    lease_id: str
    provider: str
    tenant_id: str
    user_id: str
    agent_id: str
    workspace_id: str
    status: str = "active"
    profile: dict[str, str] = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    expires_at: float | None = None

    @classmethod
    def from_lease(cls, lease: SandboxLease) -> "SandboxLeaseRecord":
        workspace = lease.workspace
        return cls(
            lease_id=lease.lease_id,
            provider=lease.provider,
            tenant_id=workspace.tenant_id,
            user_id=workspace.user_id,
            agent_id=workspace.agent_id,
            workspace_id=workspace.workspace_id,
            profile=_profile_to_dict(lease.profile),
            metadata={key: str(value) for key, value in lease.metadata.items()},
            created_at=lease.created_at,
            expires_at=lease.expires_at,
        )

    @classmethod
    def for_workspace(
        cls,
        lease_id: str,
        provider: str,
        workspace: WorkspaceContext,
        profile: SandboxProfile,
    ) -> "SandboxLeaseRecord":
        return cls(
            lease_id=lease_id,
            provider=provider,
            tenant_id=workspace.tenant_id,
            user_id=workspace.user_id,
            agent_id=workspace.agent_id,
            workspace_id=workspace.workspace_id,
            profile=_profile_to_dict(profile),
        )

    def with_status(self, status: str) -> "SandboxLeaseRecord":
        return replace(self, status=status, updated_at=time.time())


@dataclass(frozen=True)
class SandboxEventRecord:
    lease_id: str
    event_type: str
    payload: dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)


class SandboxStore(Protocol):
    async def save_lease(self, lease: SandboxLeaseRecord) -> None:
        raise NotImplementedError()

    async def load_lease(self, lease_id: str) -> Optional[SandboxLeaseRecord]:
        raise NotImplementedError()

    async def mark_released(self, lease_id: str) -> None:
        raise NotImplementedError()

    async def record_event(self, event: SandboxEventRecord) -> None:
        raise NotImplementedError()

    async def list_events(self, lease_id: str) -> List[SandboxEventRecord]:
        raise NotImplementedError()


class InMemorySandboxStore:
    def __init__(self):
        self._leases: Dict[str, SandboxLeaseRecord] = {}
        self._events: Dict[str, list[SandboxEventRecord]] = {}

    async def save_lease(self, lease: SandboxLeaseRecord) -> None:
        self._leases[lease.lease_id] = replace(lease, updated_at=time.time())

    async def load_lease(self, lease_id: str) -> Optional[SandboxLeaseRecord]:
        return self._leases.get(lease_id)

    async def mark_released(self, lease_id: str) -> None:
        lease = self._leases.get(lease_id)
        if lease is not None:
            self._leases[lease_id] = lease.with_status("released")

    async def record_event(self, event: SandboxEventRecord) -> None:
        self._events.setdefault(event.lease_id, []).append(event)

    async def list_events(self, lease_id: str) -> List[SandboxEventRecord]:
        return list(self._events.get(lease_id, []))


class SQLiteSandboxStore:
    def __init__(self, database: SQLiteDatabase):
        self.database = database

    async def save_lease(self, lease: SandboxLeaseRecord) -> None:
        record = replace(lease, updated_at=time.time())
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO sandbox_leases (
                    lease_id, provider, tenant_id, user_id, agent_id, workspace_id,
                    status, profile_json, metadata_json, created_at, updated_at, expires_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(lease_id) DO UPDATE SET
                    status = excluded.status,
                    profile_json = excluded.profile_json,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at,
                    expires_at = excluded.expires_at
                """,
                (
                    record.lease_id,
                    record.provider,
                    record.tenant_id,
                    record.user_id,
                    record.agent_id,
                    record.workspace_id,
                    record.status,
                    json_dumps(record.profile),
                    json_dumps(record.metadata),
                    record.created_at,
                    record.updated_at,
                    record.expires_at,
                ),
            )

    async def load_lease(self, lease_id: str) -> Optional[SandboxLeaseRecord]:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM sandbox_leases WHERE lease_id = ?", (lease_id,)).fetchone()
        return _lease_from_row(row) if row is not None else None

    async def mark_released(self, lease_id: str) -> None:
        with self.database.connect() as connection:
            connection.execute(
                "UPDATE sandbox_leases SET status = ?, updated_at = ? WHERE lease_id = ?",
                ("released", time.time(), lease_id),
            )

    async def record_event(self, event: SandboxEventRecord) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO sandbox_events (lease_id, event_type, payload_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (event.lease_id, event.event_type, json_dumps(event.payload), event.created_at),
            )

    async def list_events(self, lease_id: str) -> List[SandboxEventRecord]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM sandbox_events
                WHERE lease_id = ?
                ORDER BY created_at ASC, id ASC
                """,
                (lease_id,),
            ).fetchall()
        return [_event_from_row(row) for row in rows]


def _profile_to_dict(profile: SandboxProfile) -> dict[str, str]:
    return {
        "provider": profile.provider,
        "image": profile.image,
        "network_mode": profile.network_mode,
        "memory": profile.memory,
        "cpus": profile.cpus,
        "ttl_seconds": str(profile.ttl_seconds),
        "workdir": profile.workdir,
    }


def _lease_from_row(row) -> SandboxLeaseRecord:
    return SandboxLeaseRecord(
        lease_id=str(row["lease_id"]),
        provider=str(row["provider"]),
        tenant_id=str(row["tenant_id"]),
        user_id=str(row["user_id"]),
        agent_id=str(row["agent_id"]),
        workspace_id=str(row["workspace_id"]),
        status=str(row["status"]),
        profile={key: str(value) for key, value in json_dict(row["profile_json"]).items()},
        metadata={key: str(value) for key, value in json_dict(row["metadata_json"]).items()},
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
        expires_at=None if row["expires_at"] is None else float(row["expires_at"]),
    )


def _event_from_row(row) -> SandboxEventRecord:
    return SandboxEventRecord(
        lease_id=str(row["lease_id"]),
        event_type=str(row["event_type"]),
        payload={key: str(value) for key, value in json_dict(row["payload_json"]).items()},
        created_at=float(row["created_at"]),
    )
