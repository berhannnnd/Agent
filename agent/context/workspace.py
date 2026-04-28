from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List


@dataclass(frozen=True)
class WorkspaceContext:
    tenant_id: str
    user_id: str
    agent_id: str
    workspace_id: str
    root: Path
    path: Path
    instruction_paths: tuple[Path, ...] = ()

    def instruction_files(self) -> List[Path]:
        if self.instruction_paths:
            return list(self.instruction_paths)
        return [
            self.root / self.tenant_id / self.user_id / "AGENTS.md",
            self.root / self.tenant_id / self.user_id / self.agent_id / "AGENTS.md",
            self.path / "AGENTS.md",
        ]
