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


def resolve_database_path(root_path: Path, configured_path: str) -> Path:
    path = Path(configured_path or ".agents/agents.db")
    return path if path.is_absolute() else Path(root_path) / path


SCHEMA = """
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
"""
