from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Protocol

from agent.persistence import SQLiteDatabase
from agent.schema import ToolCall
from agent.governance.tool_impact import describe_tool_impact


@dataclass(frozen=True)
class ApprovalAuditRecord:
    run_id: str
    approval_id: str
    tool_name: str
    approved: bool
    decision: str = "allow_once"
    reason: str = ""
    tool_call: dict[str, Any] = field(default_factory=dict)
    impact: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    @classmethod
    def from_tool_call(
        cls,
        *,
        run_id: str,
        call: ToolCall,
        approved: bool,
        decision: str = "allow_once",
        reason: str = "",
    ) -> "ApprovalAuditRecord":
        return cls(
            run_id=run_id,
            approval_id=call.id or call.name,
            tool_name=call.name,
            approved=approved,
            decision=decision,
            reason=reason,
            tool_call=call.to_dict(),
            impact=describe_tool_impact(call).to_dict(),
        )

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "approval_id": self.approval_id,
            "tool_name": self.tool_name,
            "approved": self.approved,
            "decision": self.decision,
            "reason": self.reason,
            "tool_call": dict(self.tool_call),
            "impact": dict(self.impact),
            "created_at": self.created_at,
        }


class ApprovalAuditStore(Protocol):
    async def record(self, audit: ApprovalAuditRecord) -> None:
        raise NotImplementedError()

    async def list_for_run(self, run_id: str) -> List[ApprovalAuditRecord]:
        raise NotImplementedError()


class NullApprovalAuditStore:
    async def record(self, audit: ApprovalAuditRecord) -> None:
        return None

    async def list_for_run(self, run_id: str) -> List[ApprovalAuditRecord]:
        return []


class InMemoryApprovalAuditStore:
    def __init__(self):
        self._records: Dict[str, List[ApprovalAuditRecord]] = {}

    async def record(self, audit: ApprovalAuditRecord) -> None:
        self._records.setdefault(audit.run_id, []).append(audit)

    async def list_for_run(self, run_id: str) -> List[ApprovalAuditRecord]:
        return list(self._records.get(run_id, []))


class SQLiteApprovalAuditStore:
    def __init__(self, database: SQLiteDatabase):
        self.database = database

    async def record(self, audit: ApprovalAuditRecord) -> None:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO approval_audit (
                    run_id, approval_id, tool_name, approved, decision, reason, tool_call_json, impact_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    audit.run_id,
                    audit.approval_id,
                    audit.tool_name,
                    1 if audit.approved else 0,
                    audit.decision,
                    audit.reason,
                    json.dumps(audit.tool_call, ensure_ascii=False, sort_keys=True),
                    json.dumps(audit.impact, ensure_ascii=False, sort_keys=True),
                    audit.created_at,
                ),
            )

    async def list_for_run(self, run_id: str) -> List[ApprovalAuditRecord]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM approval_audit WHERE run_id = ? ORDER BY id ASC",
                (run_id,),
            ).fetchall()
        return [
            ApprovalAuditRecord(
                run_id=str(row["run_id"]),
                approval_id=str(row["approval_id"]),
                tool_name=str(row["tool_name"]),
                approved=bool(row["approved"]),
                decision=str(row["decision"] or "allow_once"),
                reason=str(row["reason"] or ""),
                tool_call=dict(json.loads(row["tool_call_json"] or "{}")),
                impact=dict(json.loads(row["impact_json"] or "{}")),
                created_at=float(row["created_at"]),
            )
            for row in rows
        ]
