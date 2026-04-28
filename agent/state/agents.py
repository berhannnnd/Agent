from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Protocol, Tuple

from agent.specs.spec import AgentSpec
from agent.persistence import SQLiteDatabase, json_dict, json_dumps


@dataclass(frozen=True)
class AgentProfile:
    tenant_id: str
    user_id: str
    agent_id: str
    name: str = ""
    spec: dict = field(default_factory=dict)
    metadata: dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @classmethod
    def from_spec(cls, spec: AgentSpec, name: str = "") -> "AgentProfile":
        resolved = spec.with_workspace_defaults()
        return cls(
            tenant_id=resolved.workspace.tenant_id or "default",
            user_id=resolved.workspace.user_id or "anonymous",
            agent_id=resolved.agent_id or resolved.workspace.agent_id or "default",
            name=name,
            spec=resolved.to_dict(include_secrets=False),
            metadata={key: str(value) for key, value in resolved.metadata.items()},
        )

    def with_update(self) -> "AgentProfile":
        return replace(self, updated_at=time.time())

    def to_agent_spec(self) -> AgentSpec:
        return AgentSpec.from_dict(self.spec)

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "name": self.name,
            "spec": dict(self.spec),
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class AgentProfileStore(Protocol):
    async def save(self, profile: AgentProfile) -> None:
        raise NotImplementedError()

    async def load(self, tenant_id: str, user_id: str, agent_id: str) -> Optional[AgentProfile]:
        raise NotImplementedError()

    async def list_for_user(self, tenant_id: str, user_id: str) -> List[AgentProfile]:
        raise NotImplementedError()


class InMemoryAgentProfileStore:
    def __init__(self):
        self._profiles: Dict[Tuple[str, str, str], AgentProfile] = {}

    async def save(self, profile: AgentProfile) -> None:
        self._profiles[(profile.tenant_id, profile.user_id, profile.agent_id)] = profile.with_update()

    async def load(self, tenant_id: str, user_id: str, agent_id: str) -> Optional[AgentProfile]:
        return self._profiles.get((tenant_id, user_id, agent_id))

    async def list_for_user(self, tenant_id: str, user_id: str) -> List[AgentProfile]:
        return sorted(
            [
                profile
                for key, profile in self._profiles.items()
                if key[0] == tenant_id and key[1] == user_id
            ],
            key=lambda profile: profile.agent_id,
        )


class SQLiteAgentProfileStore:
    def __init__(self, database: SQLiteDatabase):
        self.database = database

    async def save(self, profile: AgentProfile) -> None:
        record = profile.with_update()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO agent_profiles (
                    tenant_id, user_id, agent_id, name, spec_json,
                    metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, user_id, agent_id) DO UPDATE SET
                    name = excluded.name,
                    spec_json = excluded.spec_json,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    record.tenant_id,
                    record.user_id,
                    record.agent_id,
                    record.name,
                    json_dumps(record.spec),
                    json_dumps(record.metadata),
                    record.created_at,
                    record.updated_at,
                ),
            )

    async def load(self, tenant_id: str, user_id: str, agent_id: str) -> Optional[AgentProfile]:
        with self.database.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM agent_profiles
                WHERE tenant_id = ? AND user_id = ? AND agent_id = ?
                """,
                (tenant_id, user_id, agent_id),
            ).fetchone()
        return _profile_from_row(row) if row is not None else None

    async def list_for_user(self, tenant_id: str, user_id: str) -> List[AgentProfile]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM agent_profiles
                WHERE tenant_id = ? AND user_id = ?
                ORDER BY agent_id ASC
                """,
                (tenant_id, user_id),
            ).fetchall()
        return [_profile_from_row(row) for row in rows]


def _profile_from_row(row) -> AgentProfile:
    return AgentProfile(
        tenant_id=str(row["tenant_id"]),
        user_id=str(row["user_id"]),
        agent_id=str(row["agent_id"]),
        name=str(row["name"] or ""),
        spec=json_dict(row["spec_json"]),
        metadata={key: str(value) for key, value in json_dict(row["metadata_json"]).items()},
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
    )
