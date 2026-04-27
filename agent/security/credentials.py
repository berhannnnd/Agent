from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Protocol
from uuid import uuid4

from agent.persistence import SQLiteDatabase, json_dict, json_dumps


@dataclass(frozen=True)
class CredentialRef:
    credential_id: str
    tenant_id: str
    provider: str
    name: str
    secret_ref: str
    user_id: str = ""
    agent_id: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    @classmethod
    def create(
        cls,
        *,
        tenant_id: str,
        provider: str,
        name: str,
        secret_ref: str,
        user_id: str = "",
        agent_id: str = "",
        metadata: dict[str, str] | None = None,
    ) -> "CredentialRef":
        return cls(
            credential_id="cred_%s" % uuid4().hex,
            tenant_id=tenant_id,
            user_id=user_id,
            agent_id=agent_id,
            provider=provider,
            name=name,
            secret_ref=secret_ref,
            metadata=dict(metadata or {}),
        )

    def with_update(self) -> "CredentialRef":
        return replace(self, updated_at=time.time())

    def to_dict(self) -> dict:
        return {
            "credential_id": self.credential_id,
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "provider": self.provider,
            "name": self.name,
            "secret_ref": self.secret_ref,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class CredentialRefStore(Protocol):
    async def save(self, credential: CredentialRef) -> None:
        raise NotImplementedError()

    async def load(self, credential_id: str) -> Optional[CredentialRef]:
        raise NotImplementedError()

    async def list_for_scope(self, tenant_id: str, user_id: str = "", agent_id: str = "") -> List[CredentialRef]:
        raise NotImplementedError()


class InMemoryCredentialRefStore:
    def __init__(self):
        self._credentials: Dict[str, CredentialRef] = {}

    async def save(self, credential: CredentialRef) -> None:
        self._credentials[credential.credential_id] = credential.with_update()

    async def load(self, credential_id: str) -> Optional[CredentialRef]:
        return self._credentials.get(credential_id)

    async def list_for_scope(self, tenant_id: str, user_id: str = "", agent_id: str = "") -> List[CredentialRef]:
        return sorted(
            [
                credential
                for credential in self._credentials.values()
                if _credential_matches(credential, tenant_id, user_id, agent_id)
            ],
            key=lambda credential: (credential.provider, credential.name, credential.credential_id),
        )


class SQLiteCredentialRefStore:
    def __init__(self, database: SQLiteDatabase):
        self.database = database

    async def save(self, credential: CredentialRef) -> None:
        record = credential.with_update()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO credential_refs (
                    credential_id, tenant_id, user_id, agent_id, provider,
                    name, secret_ref, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(credential_id) DO UPDATE SET
                    tenant_id = excluded.tenant_id,
                    user_id = excluded.user_id,
                    agent_id = excluded.agent_id,
                    provider = excluded.provider,
                    name = excluded.name,
                    secret_ref = excluded.secret_ref,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    record.credential_id,
                    record.tenant_id,
                    record.user_id,
                    record.agent_id,
                    record.provider,
                    record.name,
                    record.secret_ref,
                    json_dumps(record.metadata),
                    record.created_at,
                    record.updated_at,
                ),
            )

    async def load(self, credential_id: str) -> Optional[CredentialRef]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM credential_refs WHERE credential_id = ?",
                (credential_id,),
            ).fetchone()
        return _credential_from_row(row) if row is not None else None

    async def list_for_scope(self, tenant_id: str, user_id: str = "", agent_id: str = "") -> List[CredentialRef]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM credential_refs
                WHERE tenant_id = ?
                  AND (user_id = '' OR user_id = ?)
                  AND (agent_id = '' OR agent_id = ?)
                ORDER BY provider ASC, name ASC, credential_id ASC
                """,
                (tenant_id, user_id, agent_id),
            ).fetchall()
        return [_credential_from_row(row) for row in rows]


def _credential_matches(credential: CredentialRef, tenant_id: str, user_id: str, agent_id: str) -> bool:
    return (
        credential.tenant_id == tenant_id
        and credential.user_id in ("", user_id)
        and credential.agent_id in ("", agent_id)
    )


def _credential_from_row(row) -> CredentialRef:
    return CredentialRef(
        credential_id=str(row["credential_id"]),
        tenant_id=str(row["tenant_id"]),
        user_id=str(row["user_id"] or ""),
        agent_id=str(row["agent_id"] or ""),
        provider=str(row["provider"]),
        name=str(row["name"]),
        secret_ref=str(row["secret_ref"]),
        metadata={key: str(value) for key, value in json_dict(row["metadata_json"]).items()},
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
    )
