from __future__ import annotations

import sqlite3
from pathlib import Path


class SQLiteDatabase:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def initialize(self) -> None:
        with self.connect() as connection:
            connection.executescript(SCHEMA)
            _ensure_columns(connection, "sandbox_leases", SANDBOX_LEASE_COLUMNS)
            _ensure_columns(connection, "sandbox_events", SANDBOX_EVENT_COLUMNS)


def resolve_database_path(root_path: Path, configured_path: str) -> Path:
    path = Path(configured_path or ".agents/agents.db")
    return path if path.is_absolute() else Path(root_path) / path


def _ensure_columns(connection: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    existing = {str(row["name"]) for row in connection.execute("PRAGMA table_info(%s)" % table).fetchall()}
    for name, definition in columns.items():
        if name not in existing:
            connection.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, name, definition))


SANDBOX_LEASE_COLUMNS = {
    "run_id": "TEXT NOT NULL DEFAULT ''",
    "task_id": "TEXT NOT NULL DEFAULT ''",
}


SANDBOX_EVENT_COLUMNS = {
    "run_id": "TEXT NOT NULL DEFAULT ''",
    "task_id": "TEXT NOT NULL DEFAULT ''",
    "tool_call_id": "TEXT NOT NULL DEFAULT ''",
    "tool_name": "TEXT NOT NULL DEFAULT ''",
    "status": "TEXT NOT NULL DEFAULT ''",
    "duration_ms": "REAL NOT NULL DEFAULT 0",
}


SCHEMA = """
CREATE TABLE IF NOT EXISTS tenants (
    tenant_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    display_name TEXT NOT NULL DEFAULT '',
    email TEXT NOT NULL DEFAULT '',
    roles_json TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY(tenant_id, user_id),
    FOREIGN KEY(tenant_id) REFERENCES tenants(tenant_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS agent_profiles (
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    spec_json TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY(tenant_id, user_id, agent_id)
);

CREATE TABLE IF NOT EXISTS workspace_records (
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    metadata_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    PRIMARY KEY(tenant_id, user_id, agent_id, workspace_id)
);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL DEFAULT '',
    tenant_id TEXT NOT NULL DEFAULT '',
    user_id TEXT NOT NULL DEFAULT '',
    workspace_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    metadata_json TEXT NOT NULL,
    spec_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS runtime_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    event_index INTEGER NOT NULL,
    type TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL,
    raw_json TEXT,
    created_at REAL NOT NULL,
    UNIQUE(run_id, event_index),
    FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS runtime_checkpoints (
    run_id TEXT PRIMARY KEY,
    step TEXT NOT NULL,
    iteration INTEGER NOT NULL,
    messages_json TEXT NOT NULL,
    tool_results_json TEXT NOT NULL,
    events_json TEXT NOT NULL,
    pending_tool_calls_json TEXT NOT NULL,
    tool_approvals_json TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS approval_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    approval_id TEXT NOT NULL,
    tool_name TEXT NOT NULL DEFAULT '',
    approved INTEGER NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    tool_call_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS trace_spans (
    span_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    parent_span_id TEXT NOT NULL DEFAULT '',
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at REAL NOT NULL,
    ended_at REAL,
    attributes_json TEXT NOT NULL,
    error TEXT NOT NULL DEFAULT '',
    FOREIGN KEY(run_id) REFERENCES runs(run_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_trace_spans_run_id_started_at
ON trace_spans(run_id, started_at);

CREATE TABLE IF NOT EXISTS memory_records (
    memory_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    agent_id TEXT NOT NULL DEFAULT '',
    workspace_id TEXT NOT NULL DEFAULT '',
    scope TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memory_records_context
ON memory_records(tenant_id, user_id, agent_id, workspace_id, created_at);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    input TEXT NOT NULL,
    agent_id TEXT NOT NULL DEFAULT '',
    tenant_id TEXT NOT NULL DEFAULT '',
    user_id TEXT NOT NULL DEFAULT '',
    workspace_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    metadata_json TEXT NOT NULL,
    spec_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_tasks_scope
ON tasks(tenant_id, user_id, agent_id, created_at);

CREATE TABLE IF NOT EXISTS task_steps (
    step_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    step_index INTEGER NOT NULL,
    name TEXT NOT NULL,
    input TEXT NOT NULL DEFAULT '',
    run_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    output TEXT NOT NULL DEFAULT '',
    error TEXT NOT NULL DEFAULT '',
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    metadata_json TEXT NOT NULL,
    UNIQUE(task_id, step_index),
    FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_task_steps_task
ON task_steps(task_id, step_index);

CREATE TABLE IF NOT EXISTS task_attempts (
    attempt_id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    step_id TEXT NOT NULL,
    run_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    started_at REAL NOT NULL,
    ended_at REAL,
    error TEXT NOT NULL DEFAULT '',
    metadata_json TEXT NOT NULL,
    FOREIGN KEY(task_id) REFERENCES tasks(task_id) ON DELETE CASCADE,
    FOREIGN KEY(step_id) REFERENCES task_steps(step_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_task_attempts_step
ON task_attempts(step_id, started_at);

CREATE TABLE IF NOT EXISTS sandbox_leases (
    lease_id TEXT PRIMARY KEY,
    provider TEXT NOT NULL,
    tenant_id TEXT NOT NULL DEFAULT '',
    user_id TEXT NOT NULL DEFAULT '',
    agent_id TEXT NOT NULL DEFAULT '',
    workspace_id TEXT NOT NULL DEFAULT '',
    run_id TEXT NOT NULL DEFAULT '',
    task_id TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    profile_json TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    expires_at REAL
);

CREATE INDEX IF NOT EXISTS idx_sandbox_leases_scope
ON sandbox_leases(tenant_id, user_id, agent_id, workspace_id, created_at);

CREATE INDEX IF NOT EXISTS idx_sandbox_leases_run
ON sandbox_leases(run_id, task_id, created_at);

CREATE TABLE IF NOT EXISTS sandbox_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lease_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    run_id TEXT NOT NULL DEFAULT '',
    task_id TEXT NOT NULL DEFAULT '',
    tool_call_id TEXT NOT NULL DEFAULT '',
    tool_name TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT '',
    duration_ms REAL NOT NULL DEFAULT 0,
    payload_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    FOREIGN KEY(lease_id) REFERENCES sandbox_leases(lease_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sandbox_events_lease
ON sandbox_events(lease_id, created_at);

CREATE INDEX IF NOT EXISTS idx_sandbox_events_run
ON sandbox_events(run_id, task_id, created_at);

CREATE TABLE IF NOT EXISTS sandbox_workspace_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    lease_id TEXT NOT NULL,
    run_id TEXT NOT NULL DEFAULT '',
    task_id TEXT NOT NULL DEFAULT '',
    phase TEXT NOT NULL DEFAULT '',
    file_count INTEGER NOT NULL DEFAULT 0,
    total_bytes INTEGER NOT NULL DEFAULT 0,
    manifest_json TEXT NOT NULL,
    diff_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    FOREIGN KEY(lease_id) REFERENCES sandbox_leases(lease_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sandbox_workspace_snapshots_run
ON sandbox_workspace_snapshots(run_id, task_id, created_at);

CREATE TABLE IF NOT EXISTS credential_refs (
    credential_id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL DEFAULT '',
    agent_id TEXT NOT NULL DEFAULT '',
    provider TEXT NOT NULL,
    name TEXT NOT NULL,
    secret_ref TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_credential_refs_scope
ON credential_refs(tenant_id, user_id, agent_id, provider, name);
"""
