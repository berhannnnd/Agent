from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent.context.workspace import WorkspaceContext


SKIPPED_PARTS = {".git", "__pycache__", ".venv", "node_modules", "artifacts"}
ARTIFACT_DIRS = (
    "artifacts",
    "artifacts/downloads",
    "artifacts/screenshots",
    "artifacts/logs",
    "artifacts/snapshots",
)


@dataclass(frozen=True)
class WorkspaceArtifacts:
    root: str = "artifacts"
    downloads: str = "artifacts/downloads"
    screenshots: str = "artifacts/screenshots"
    logs: str = "artifacts/logs"
    snapshots: str = "artifacts/snapshots"

    @classmethod
    def ensure(cls, workspace: WorkspaceContext) -> "WorkspaceArtifacts":
        for path in ARTIFACT_DIRS:
            (workspace.path / path).mkdir(parents=True, exist_ok=True)
        return cls()

    def to_dict(self) -> dict[str, str]:
        return {
            "root": self.root,
            "downloads": self.downloads,
            "screenshots": self.screenshots,
            "logs": self.logs,
            "snapshots": self.snapshots,
        }


@dataclass(frozen=True)
class WorkspaceFileState:
    path: str
    size: int
    mtime: float
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "size": self.size,
            "mtime": self.mtime,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class WorkspaceSnapshot:
    captured_at: float
    files: dict[str, WorkspaceFileState] = field(default_factory=dict)

    @classmethod
    def capture(cls, workspace: WorkspaceContext) -> "WorkspaceSnapshot":
        root = workspace.path.resolve()
        files: dict[str, WorkspaceFileState] = {}
        if not root.exists():
            return cls(captured_at=time.time(), files=files)
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            relative = path.resolve().relative_to(root).as_posix()
            if _should_skip(relative):
                continue
            try:
                stat = path.stat()
                digest = _sha256(path)
            except OSError:
                continue
            files[relative] = WorkspaceFileState(
                path=relative,
                size=int(stat.st_size),
                mtime=float(stat.st_mtime),
                sha256=digest,
            )
        return cls(captured_at=time.time(), files=files)

    def diff(self, other: "WorkspaceSnapshot") -> dict[str, Any]:
        before = self.files
        after = other.files
        created = sorted(path for path in after if path not in before)
        deleted = sorted(path for path in before if path not in after)
        modified = sorted(path for path in after if path in before and after[path].sha256 != before[path].sha256)
        return {
            "created": created,
            "modified": modified,
            "deleted": deleted,
            "file_count_before": len(before),
            "file_count_after": len(after),
            "total_bytes_before": sum(item.size for item in before.values()),
            "total_bytes_after": sum(item.size for item in after.values()),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "captured_at": self.captured_at,
            "files": {path: state.to_dict() for path, state in self.files.items()},
        }


def _should_skip(relative_path: str) -> bool:
    return any(part in SKIPPED_PARTS for part in Path(relative_path).parts)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
