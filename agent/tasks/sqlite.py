from __future__ import annotations

from typing import List, Optional

from agent.persistence import SQLiteDatabase, json_dict, json_dumps
from agent.specs import AgentSpec
from agent.tasks.types import (
    TaskAttemptRecord,
    TaskAttemptStatus,
    TaskRecord,
    TaskStatus,
    TaskStepRecord,
    TaskStepStatus,
)


class SQLiteTaskStore:
    def __init__(self, database: SQLiteDatabase):
        self.database = database

    async def create_task(
        self,
        spec: AgentSpec,
        title: str,
        input: str,
        metadata: dict[str, str] | None = None,
    ) -> TaskRecord:
        task = TaskRecord.create(spec=spec, title=title, input=input, metadata=metadata)
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO tasks (
                    task_id, title, input, agent_id, tenant_id, user_id, workspace_id,
                    status, created_at, updated_at, metadata_json, spec_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.title,
                    task.input,
                    task.agent_id,
                    task.tenant_id,
                    task.user_id,
                    task.workspace_id,
                    task.status.value,
                    task.created_at,
                    task.updated_at,
                    json_dumps(task.metadata),
                    json_dumps(task.spec),
                ),
            )
        return task

    async def load_task(self, task_id: str) -> Optional[TaskRecord]:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        return _task_from_row(row) if row is not None else None

    async def list_tasks(self, tenant_id: str, user_id: str = "", agent_id: str = "") -> List[TaskRecord]:
        with self.database.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM tasks
                WHERE tenant_id = ?
                  AND (user_id = '' OR user_id = ?)
                  AND (agent_id = '' OR agent_id = ?)
                ORDER BY created_at ASC, task_id ASC
                """,
                (tenant_id, user_id, agent_id),
            ).fetchall()
        return [_task_from_row(row) for row in rows]

    async def set_task_status(self, task_id: str, status: TaskStatus) -> Optional[TaskRecord]:
        with self.database.connect() as connection:
            task = connection.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            if task is None:
                return None
            updated = _task_from_row(task).with_status(status)
            connection.execute(
                "UPDATE tasks SET status = ?, updated_at = ? WHERE task_id = ?",
                (updated.status.value, updated.updated_at, task_id),
            )
        return await self.load_task(task_id)

    async def add_step(self, step: TaskStepRecord) -> TaskStepRecord:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO task_steps (
                    step_id, task_id, step_index, name, input, run_id, status,
                    output, error, created_at, updated_at, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _step_values(step),
            )
        return step

    async def load_step(self, step_id: str) -> Optional[TaskStepRecord]:
        with self.database.connect() as connection:
            row = connection.execute("SELECT * FROM task_steps WHERE step_id = ?", (step_id,)).fetchone()
        return _step_from_row(row) if row is not None else None

    async def list_steps(self, task_id: str) -> List[TaskStepRecord]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM task_steps WHERE task_id = ? ORDER BY step_index ASC, created_at ASC, step_id ASC",
                (task_id,),
            ).fetchall()
        return [_step_from_row(row) for row in rows]

    async def load_step_for_run(self, run_id: str) -> Optional[TaskStepRecord]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM task_steps WHERE run_id = ? ORDER BY created_at DESC, step_id DESC LIMIT 1",
                (run_id,),
            ).fetchone()
        return _step_from_row(row) if row is not None else None

    async def update_step_status(
        self,
        step_id: str,
        status: TaskStepStatus,
        *,
        output: str = "",
        error: str = "",
    ) -> Optional[TaskStepRecord]:
        step = await self.load_step(step_id)
        if step is None:
            return None
        updated = step.with_status(status, output=output, error=error)
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE task_steps
                SET status = ?, output = ?, error = ?, updated_at = ?
                WHERE step_id = ?
                """,
                (updated.status.value, updated.output, updated.error, updated.updated_at, step_id),
            )
        return updated

    async def add_attempt(self, attempt: TaskAttemptRecord) -> TaskAttemptRecord:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT INTO task_attempts (
                    attempt_id, task_id, step_id, run_id, status,
                    started_at, ended_at, error, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _attempt_values(attempt),
            )
        return attempt

    async def list_attempts(self, step_id: str) -> List[TaskAttemptRecord]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM task_attempts WHERE step_id = ? ORDER BY started_at ASC, attempt_id ASC",
                (step_id,),
            ).fetchall()
        return [_attempt_from_row(row) for row in rows]

    async def finish_attempt(
        self,
        attempt_id: str,
        status: TaskAttemptStatus,
        error: str = "",
    ) -> Optional[TaskAttemptRecord]:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM task_attempts WHERE attempt_id = ?",
                (attempt_id,),
            ).fetchone()
            if row is None:
                return None
            updated = _attempt_from_row(row).finish(status, error=error)
            connection.execute(
                """
                UPDATE task_attempts
                SET status = ?, ended_at = ?, error = ?
                WHERE attempt_id = ?
                """,
                (updated.status.value, updated.ended_at, updated.error, attempt_id),
            )
        return updated


def _task_from_row(row) -> TaskRecord:
    return TaskRecord(
        task_id=str(row["task_id"]),
        title=str(row["title"]),
        input=str(row["input"]),
        agent_id=str(row["agent_id"] or ""),
        tenant_id=str(row["tenant_id"] or ""),
        user_id=str(row["user_id"] or ""),
        workspace_id=str(row["workspace_id"] or ""),
        status=TaskStatus(str(row["status"])),
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
        metadata={key: str(value) for key, value in json_dict(row["metadata_json"]).items()},
        spec=json_dict(row["spec_json"]),
    )


def _step_values(step: TaskStepRecord) -> tuple:
    return (
        step.step_id,
        step.task_id,
        step.index,
        step.name,
        step.input,
        step.run_id,
        step.status.value,
        step.output,
        step.error,
        step.created_at,
        step.updated_at,
        json_dumps(step.metadata),
    )


def _step_from_row(row) -> TaskStepRecord:
    return TaskStepRecord(
        step_id=str(row["step_id"]),
        task_id=str(row["task_id"]),
        index=int(row["step_index"]),
        name=str(row["name"]),
        input=str(row["input"] or ""),
        run_id=str(row["run_id"] or ""),
        status=TaskStepStatus(str(row["status"])),
        output=str(row["output"] or ""),
        error=str(row["error"] or ""),
        created_at=float(row["created_at"]),
        updated_at=float(row["updated_at"]),
        metadata={key: str(value) for key, value in json_dict(row["metadata_json"]).items()},
    )


def _attempt_values(attempt: TaskAttemptRecord) -> tuple:
    return (
        attempt.attempt_id,
        attempt.task_id,
        attempt.step_id,
        attempt.run_id,
        attempt.status.value,
        attempt.started_at,
        attempt.ended_at,
        attempt.error,
        json_dumps(attempt.metadata),
    )


def _attempt_from_row(row) -> TaskAttemptRecord:
    return TaskAttemptRecord(
        attempt_id=str(row["attempt_id"]),
        task_id=str(row["task_id"]),
        step_id=str(row["step_id"]),
        run_id=str(row["run_id"] or ""),
        status=TaskAttemptStatus(str(row["status"])),
        started_at=float(row["started_at"]),
        ended_at=float(row["ended_at"]) if row["ended_at"] is not None else None,
        error=str(row["error"] or ""),
        metadata={key: str(value) for key, value in json_dict(row["metadata_json"]).items()},
    )
