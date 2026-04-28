from __future__ import annotations

import json
from typing import Dict, List, Optional

from agent.persistence import SQLiteDatabase
from agent.governance.tracing.types import TraceSpan, TraceStatus


class NullTraceStore:
    async def save_span(self, span: TraceSpan) -> None:
        return None

    async def load_span(self, span_id: str) -> Optional[TraceSpan]:
        return None

    async def list_for_run(self, run_id: str) -> List[TraceSpan]:
        return []


class InMemoryTraceStore:
    def __init__(self):
        self._spans: Dict[str, TraceSpan] = {}

    async def save_span(self, span: TraceSpan) -> None:
        self._spans[span.span_id] = span

    async def load_span(self, span_id: str) -> Optional[TraceSpan]:
        return self._spans.get(span_id)

    async def list_for_run(self, run_id: str) -> List[TraceSpan]:
        return sorted(
            [span for span in self._spans.values() if span.run_id == run_id],
            key=lambda span: (span.started_at, span.span_id),
        )


class SQLiteTraceStore:
    def __init__(self, database: SQLiteDatabase):
        self.database = database

    async def save_span(self, span: TraceSpan) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO trace_spans (
                    span_id, run_id, parent_span_id, kind, name, status,
                    started_at, ended_at, attributes_json, error
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(span_id) DO UPDATE SET
                    parent_span_id = excluded.parent_span_id,
                    kind = excluded.kind,
                    name = excluded.name,
                    status = excluded.status,
                    started_at = excluded.started_at,
                    ended_at = excluded.ended_at,
                    attributes_json = excluded.attributes_json,
                    error = excluded.error
                """,
                (
                    span.span_id,
                    span.run_id,
                    span.parent_span_id,
                    span.kind,
                    span.name,
                    span.status.value,
                    span.started_at,
                    span.ended_at,
                    json.dumps(span.attributes, ensure_ascii=False, sort_keys=True),
                    span.error,
                ),
            )

    async def load_span(self, span_id: str) -> Optional[TraceSpan]:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM trace_spans WHERE span_id = ?", (span_id,)).fetchone()
        return _span_from_row(row) if row is not None else None

    async def list_for_run(self, run_id: str) -> List[TraceSpan]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM trace_spans WHERE run_id = ? ORDER BY started_at ASC, span_id ASC",
                (run_id,),
            ).fetchall()
        return [_span_from_row(row) for row in rows]


def _span_from_row(row) -> TraceSpan:
    return TraceSpan(
        span_id=str(row["span_id"]),
        run_id=str(row["run_id"]),
        parent_span_id=str(row["parent_span_id"] or ""),
        kind=str(row["kind"]),
        name=str(row["name"]),
        status=TraceStatus(str(row["status"])),
        started_at=float(row["started_at"]),
        ended_at=float(row["ended_at"]) if row["ended_at"] is not None else None,
        attributes=dict(json.loads(row["attributes_json"] or "{}")),
        error=str(row["error"] or ""),
    )
