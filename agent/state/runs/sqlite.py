from __future__ import annotations

import json
import time
from typing import Optional

from agent.definitions import AgentSpec
from agent.persistence import SQLiteDatabase
from agent.state.runs.types import RunRecord, RunStatus
from agent.schema import RuntimeEvent


class SQLiteRunStore:
    def __init__(self, database: SQLiteDatabase):
        self.database = database

    async def create_run(self, spec: AgentSpec, run_id: str = "") -> RunRecord:
        record = RunRecord.from_spec(spec, run_id=run_id)
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO runs (
                    run_id, agent_id, tenant_id, user_id, workspace_id, status,
                    created_at, updated_at, metadata_json, spec_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.run_id,
                    record.agent_id,
                    record.tenant_id,
                    record.user_id,
                    record.workspace_id,
                    record.status.value,
                    record.created_at,
                    record.updated_at,
                    _json_dumps(record.metadata),
                    _json_dumps(record.spec),
                ),
            )
        return record

    async def load_run(self, run_id: str) -> Optional[RunRecord]:
        with self.database.connect() as connection:
            run = connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if run is None:
                return None
            events = connection.execute(
                "SELECT * FROM runtime_events WHERE run_id = ? ORDER BY event_index ASC",
                (run_id,),
            ).fetchall()
        return _record_from_sqlite(run, events)

    async def append_event(self, run_id: str, event: RuntimeEvent) -> Optional[RunRecord]:
        now = time.time()
        with self.database.connect() as connection:
            run = connection.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
            if run is None:
                return None
            event_index = int(
                connection.execute(
                    "SELECT COALESCE(MAX(event_index), -1) + 1 FROM runtime_events WHERE run_id = ?",
                    (run_id,),
                ).fetchone()[0]
            )
            connection.execute(
                """
                INSERT INTO runtime_events (
                    run_id, event_index, type, name, payload_json, raw_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    event_index,
                    event.type,
                    event.name,
                    _json_dumps(event.payload),
                    _json_dumps(event.raw) if event.raw is not None else None,
                    now,
                ),
            )
            connection.execute("UPDATE runs SET updated_at = ? WHERE run_id = ?", (now, run_id))
        return await self.load_run(run_id)

    async def set_status(self, run_id: str, status: RunStatus) -> Optional[RunRecord]:
        now = time.time()
        with self.database.connect() as connection:
            cursor = connection.execute(
                "UPDATE runs SET status = ?, updated_at = ? WHERE run_id = ?",
                (status.value, now, run_id),
            )
            if cursor.rowcount == 0:
                return None
        return await self.load_run(run_id)


def _record_from_sqlite(run, events) -> RunRecord:
    return RunRecord(
        run_id=str(run["run_id"]),
        agent_id=str(run["agent_id"]),
        tenant_id=str(run["tenant_id"]),
        user_id=str(run["user_id"]),
        workspace_id=str(run["workspace_id"]),
        status=RunStatus(str(run["status"])),
        events=[_event_from_sqlite(event) for event in events],
        created_at=float(run["created_at"]),
        updated_at=float(run["updated_at"]),
        metadata=dict(json.loads(run["metadata_json"] or "{}")),
        spec=dict(json.loads(run["spec_json"] or "{}")),
    )


def _event_from_sqlite(row) -> RuntimeEvent:
    raw_json = row["raw_json"]
    return RuntimeEvent(
        type=str(row["type"]),
        name=str(row["name"] or ""),
        payload=dict(json.loads(row["payload_json"] or "{}")),
        raw=json.loads(raw_json) if raw_json else None,
    )


def _json_dumps(value) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)
