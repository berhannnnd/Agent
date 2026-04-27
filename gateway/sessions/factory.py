from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.persistence import SQLiteDatabase, resolve_database_path
from agent.runs import InMemoryRunStore, LocalFileRunStore, RunStore, SQLiteRunStore
from agent.runtime import CheckpointStore, InMemoryCheckpointStore, SQLiteCheckpointStore
from agent.security import (
    ApprovalAuditStore,
    InMemoryApprovalAuditStore,
    SQLiteApprovalAuditStore,
)


def create_run_store(settings: Any) -> RunStore:
    store_kind = str(getattr(settings.agent, "RUN_STORE", "memory") or "memory").strip().lower()
    if store_kind == "file":
        configured_root = Path(str(getattr(settings.agent, "RUN_ROOT", ".agents/runs")))
        root = configured_root if configured_root.is_absolute() else Path(settings.server.ROOT_PATH) / configured_root
        return LocalFileRunStore(root)
    if store_kind == "sqlite":
        return SQLiteRunStore(_sqlite_database(settings))
    if store_kind == "memory":
        return InMemoryRunStore()
    raise ValueError("unsupported AGENT_RUN_STORE: %s" % store_kind)


def create_checkpoint_store(settings: Any) -> CheckpointStore:
    store_kind = str(getattr(settings.agent, "RUN_STORE", "memory") or "memory").strip().lower()
    if store_kind == "sqlite":
        return SQLiteCheckpointStore(_sqlite_database(settings))
    return InMemoryCheckpointStore()


def create_approval_audit_store(settings: Any) -> ApprovalAuditStore:
    store_kind = str(getattr(settings.agent, "RUN_STORE", "memory") or "memory").strip().lower()
    if store_kind == "sqlite":
        return SQLiteApprovalAuditStore(_sqlite_database(settings))
    return InMemoryApprovalAuditStore()


def _sqlite_database(settings: Any) -> SQLiteDatabase:
    configured_path = str(getattr(settings.agent, "DB_PATH", ".agents/agents.db"))
    path = resolve_database_path(Path(settings.server.ROOT_PATH), configured_path)
    return SQLiteDatabase(path)
