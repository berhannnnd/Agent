from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from agent.specs import AgentSpec
from agent.state.runs.types import RunRecord, RunStatus
from agent.schema import RuntimeEvent


class LocalFileRunStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    async def create_run(self, spec: AgentSpec, run_id: str = "") -> RunRecord:
        record = RunRecord.from_spec(spec, run_id=run_id)
        self._write(record)
        return record

    async def load_run(self, run_id: str) -> Optional[RunRecord]:
        path = self._path(run_id)
        if not path.exists():
            return None
        return RunRecord.from_dict(json.loads(path.read_text(encoding="utf-8")))

    async def append_event(self, run_id: str, event: RuntimeEvent) -> Optional[RunRecord]:
        record = await self.load_run(run_id)
        if record is None:
            return None
        updated = record.with_event(event)
        self._write(updated)
        return updated

    async def set_status(self, run_id: str, status: RunStatus) -> Optional[RunRecord]:
        record = await self.load_run(run_id)
        if record is None:
            return None
        updated = record.with_status(status)
        self._write(updated)
        return updated

    def _path(self, run_id: str) -> Path:
        safe = "".join(ch for ch in run_id if ch.isalnum() or ch in ("_", "-", ".")).strip(".")
        return self.root / ("%s.json" % (safe or "run"))

    def _write(self, record: RunRecord) -> None:
        path = self._path(record.run_id)
        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
        tmp_path.replace(path)
