from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from typing import Dict, List, Optional, Protocol, Tuple

from agent.persistence import SQLiteDatabase, json_dict, json_dumps, json_list


@dataclass(frozen=True)
class TenantRecord:
    tenant_id: str
    display_name: str = ""
    metadata: dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def with_update(self) -> "TenantRecord":
        return replace(self, updated_at=time.time())

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "display_name": self.display_name,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


@dataclass(frozen=True)
class UserRecord:
    tenant_id: str
    user_id: str
    display_name: str = ""
    email: str = ""
    roles: List[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def with_update(self) -> "UserRecord":
        return replace(self, updated_at=time.time())

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "display_name": self.display_name,
            "email": self.email,
            "roles": list(self.roles),
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class IdentityStore(Protocol):
    async def save_tenant(self, tenant: TenantRecord) -> None:
        raise NotImplementedError()

    async def load_tenant(self, tenant_id: str) -> Optional[TenantRecord]:
        raise NotImplementedError()

    async def save_user(self, user: UserRecord) -> None:
        raise NotImplementedError()

    async def load_user(self, tenant_id: str, user_id: str) -> Optional[UserRecord]:
        raise NotImplementedError()

    async def list_users(self, tenant_id: str) -> List[UserRecord]:
        raise NotImplementedError()


class InMemoryIdentityStore:
    def __init__(self):
        self._tenants: Dict[str, TenantRecord] = {}
        self._users: Dict[Tuple[str, str], UserRecord] = {}

    async def save_tenant(self, tenant: TenantRecord) -> None:
        self._tenants[tenant.tenant_id] = tenant.with_update()

    async def load_tenant(self, tenant_id: str) -> Optional[TenantRecord]:
        return self._tenants.get(tenant_id)

    async def save_user(self, user: UserRecord) -> None:
        self._users[(user.tenant_id, user.user_id)] = user.with_update()

    async def load_user(self, tenant_id: str, user_id: str) -> Optional[UserRecord]:
        return self._users.get((tenant_id, user_id))

    async def list_users(self, tenant_id: str) -> List[UserRecord]:
        return sorted(
            [user for key, user in self._users.items() if key[0] == tenant_id],
            key=lambda user: user.user_id,
        )


class SQLiteIdentityStore:
    def __init__(self, database: SQLiteDatabase):
        self.database = database

    async def save_tenant(self, tenant: TenantRecord) -> None:
        record = tenant.with_update()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO tenants (
                    tenant_id, display_name, metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    record.tenant_id,
                    record.display_name,
                    json_dumps(record.metadata),
                    record.created_at,
                    record.updated_at,
                ),
            )

    async def load_tenant(self, tenant_id: str) -> Optional[TenantRecord]:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM tenants WHERE tenant_id = ?", (tenant_id,)).fetchone()
        return _tenant_from_row(row) if row is not None else None

    async def save_user(self, user: UserRecord) -> None:
        record = user.with_update()
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO users (
                    tenant_id, user_id, display_name, email, roles_json,
                    metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(tenant_id, user_id) DO UPDATE SET
                    display_name = excluded.display_name,
                    email = excluded.email,
                    roles_json = excluded.roles_json,
                    metadata_json = excluded.metadata_json,
                    updated_at = excluded.updated_at
                """,
                (
                    record.tenant_id,
                    record.user_id,
                    record.display_name,
                    record.email,
                    json_dumps(record.roles),
                    json_dumps(record.metadata),
                    record.created_at,
                    record.updated_at,
                ),
            )

    async def load_user(self, tenant_id: str, user_id: str) -> Optional[UserRecord]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE tenant_id = ? AND user_id = ?",
                (tenant_id, user_id),
            ).fetchone()
        return _user_from_row(row) if row is not None else None

    async def list_users(self, tenant_id: str) -> List[UserRecord]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM users WHERE tenant_id = ? ORDER BY user_id ASC",
                (tenant_id,),
            ).fetchall()
        return [_user_from_row(row) for row in rows]


def _tenant_from_row(row) -> TenantRecord:
    return TenantRecord(
        tenant_id=str(row["tenant_id"]),
        display_name=str(row["display_name"] or ""),
        metadata={key: str(value) for key, value in json_dict(row["metadata_json"]).items()},
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
    )


def _user_from_row(row) -> UserRecord:
    return UserRecord(
        tenant_id=str(row["tenant_id"]),
        user_id=str(row["user_id"]),
        display_name=str(row["display_name"] or ""),
        email=str(row["email"] or ""),
        roles=[str(item) for item in json_list(row["roles_json"])],
        metadata={key: str(value) for key, value in json_dict(row["metadata_json"]).items()},
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
    )
