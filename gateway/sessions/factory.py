from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.audit import (
    ApprovalAuditStore,
    InMemoryApprovalAuditStore,
    SQLiteApprovalAuditStore,
)
from agent.definitions import AgentProfileStore, InMemoryAgentProfileStore, SQLiteAgentProfileStore
from agent.identity import IdentityStore, InMemoryIdentityStore, SQLiteIdentityStore
from agent.memory import InMemoryMemoryStore, MemoryStore, SQLiteMemoryStore
from agent.persistence import SQLiteDatabase, resolve_database_path
from agent.runs import InMemoryRunStore, LocalFileRunStore, RunStore, SQLiteRunStore
from agent.runtime import CheckpointStore, InMemoryCheckpointStore, SQLiteCheckpointStore
from agent.security import CredentialRefStore, InMemoryCredentialRefStore, SQLiteCredentialRefStore
from agent.storage import InMemoryWorkspaceStore, SQLiteWorkspaceStore, WorkspaceStore
from agent.tracing import InMemoryTraceStore, RuntimeTraceRecorder, SQLiteTraceStore, TraceStore


def create_run_store(settings: Any) -> RunStore:
    store_kind = _store_kind(settings)
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
    if _uses_sqlite(settings):
        return SQLiteCheckpointStore(_sqlite_database(settings))
    return InMemoryCheckpointStore()


def create_approval_audit_store(settings: Any) -> ApprovalAuditStore:
    if _uses_sqlite(settings):
        return SQLiteApprovalAuditStore(_sqlite_database(settings))
    return InMemoryApprovalAuditStore()


def create_trace_store(settings: Any) -> TraceStore:
    if _uses_sqlite(settings):
        return SQLiteTraceStore(_sqlite_database(settings))
    return InMemoryTraceStore()


def create_trace_recorder(settings: Any, store: TraceStore | None = None) -> RuntimeTraceRecorder:
    return RuntimeTraceRecorder(store or create_trace_store(settings))


def create_identity_store(settings: Any) -> IdentityStore:
    if _uses_sqlite(settings):
        return SQLiteIdentityStore(_sqlite_database(settings))
    return InMemoryIdentityStore()


def create_agent_profile_store(settings: Any) -> AgentProfileStore:
    if _uses_sqlite(settings):
        return SQLiteAgentProfileStore(_sqlite_database(settings))
    return InMemoryAgentProfileStore()


def create_workspace_store(settings: Any) -> WorkspaceStore:
    if _uses_sqlite(settings):
        return SQLiteWorkspaceStore(_sqlite_database(settings))
    return InMemoryWorkspaceStore()


def create_memory_store(settings: Any) -> MemoryStore:
    if _uses_sqlite(settings):
        return SQLiteMemoryStore(_sqlite_database(settings))
    return InMemoryMemoryStore()


def create_credential_ref_store(settings: Any) -> CredentialRefStore:
    if _uses_sqlite(settings):
        return SQLiteCredentialRefStore(_sqlite_database(settings))
    return InMemoryCredentialRefStore()


def _uses_sqlite(settings: Any) -> bool:
    return _store_kind(settings) == "sqlite"


def _store_kind(settings: Any) -> str:
    return str(getattr(settings.agent, "RUN_STORE", "memory") or "memory").strip().lower()


def _sqlite_database(settings: Any) -> SQLiteDatabase:
    configured_path = str(getattr(settings.agent, "DB_PATH", ".agents/agents.db"))
    path = resolve_database_path(Path(settings.server.ROOT_PATH), configured_path)
    return SQLiteDatabase(path)
