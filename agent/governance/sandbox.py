from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Iterable


class ToolRisk(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SandboxOperation(str, Enum):
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    PROCESS = "process"
    NETWORK = "network"


@dataclass(frozen=True)
class SandboxDecision:
    allowed: bool
    operation: SandboxOperation
    risk: ToolRisk
    reason: str = ""

    def to_dict(self) -> dict:
        payload = {
            "allowed": self.allowed,
            "operation": self.operation.value,
            "risk": self.risk.value,
        }
        if self.reason:
            payload["reason"] = self.reason
        return payload


@dataclass(frozen=True)
class SandboxPolicy:
    workspace_root: Path
    allow_file_read: bool = True
    allow_file_write: bool = False
    allow_process: bool = False
    allow_network: bool = False
    allowed_commands: tuple[str, ...] = field(default_factory=tuple)
    denied_commands: tuple[str, ...] = field(default_factory=lambda: ("rm", "sudo", "chmod", "chown", "mkfs"))
    max_output_bytes: int = 20000

    @classmethod
    def for_workspace(
        cls,
        workspace_root: Path,
        *,
        allow_file_write: bool = False,
        allow_process: bool = False,
        allow_network: bool = False,
        allowed_commands: Iterable[str] = (),
    ) -> "SandboxPolicy":
        return cls(
            workspace_root=Path(workspace_root),
            allow_file_write=allow_file_write,
            allow_process=allow_process,
            allow_network=allow_network,
            allowed_commands=tuple(command for command in allowed_commands if command),
        )

    def resolve_workspace_path(self, path: str | Path) -> Path:
        root = self.workspace_root.resolve()
        candidate = Path(path)
        resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise PermissionError("path escapes workspace: %s" % path) from exc
        return resolved

    def relative_workspace_path(self, path: str | Path) -> str:
        root = self.workspace_root.resolve()
        resolved = self.resolve_workspace_path(path)
        relative = resolved.relative_to(root)
        return relative.as_posix() or "."

    def authorize_file_read(self, path: str | Path) -> SandboxDecision:
        self.resolve_workspace_path(path)
        if not self.allow_file_read:
            return SandboxDecision(False, SandboxOperation.FILE_READ, ToolRisk.LOW, "file read disabled")
        return SandboxDecision(True, SandboxOperation.FILE_READ, ToolRisk.LOW)

    def authorize_file_write(self, path: str | Path) -> SandboxDecision:
        self.resolve_workspace_path(path)
        if not self.allow_file_write:
            return SandboxDecision(False, SandboxOperation.FILE_WRITE, ToolRisk.MEDIUM, "file write disabled")
        return SandboxDecision(True, SandboxOperation.FILE_WRITE, ToolRisk.MEDIUM)

    def authorize_process(self, command: str) -> SandboxDecision:
        program = _program_name(command)
        if not self.allow_process:
            return SandboxDecision(False, SandboxOperation.PROCESS, ToolRisk.HIGH, "process execution disabled")
        if program in self.denied_commands:
            return SandboxDecision(False, SandboxOperation.PROCESS, ToolRisk.CRITICAL, "command denied")
        if self.allowed_commands and program not in self.allowed_commands:
            return SandboxDecision(False, SandboxOperation.PROCESS, ToolRisk.HIGH, "command is not allowlisted")
        return SandboxDecision(True, SandboxOperation.PROCESS, ToolRisk.HIGH)

    def authorize_network(self) -> SandboxDecision:
        if not self.allow_network:
            return SandboxDecision(False, SandboxOperation.NETWORK, ToolRisk.HIGH, "network disabled")
        return SandboxDecision(True, SandboxOperation.NETWORK, ToolRisk.HIGH)


def classify_tool_risk(name: str) -> ToolRisk:
    if name.startswith("filesystem.read") or name.startswith("filesystem.list"):
        return ToolRisk.LOW
    if name.startswith("search."):
        return ToolRisk.LOW
    if name.startswith("filesystem.write"):
        return ToolRisk.MEDIUM
    if name.startswith("patch."):
        return ToolRisk.MEDIUM
    if name.startswith("browser.") or name.startswith("web."):
        return ToolRisk.HIGH
    if name.startswith("shell.") or name.startswith("git.") or name.startswith("test."):
        return ToolRisk.HIGH
    if name.startswith("mcp_"):
        return ToolRisk.MEDIUM
    return ToolRisk.MEDIUM


def _program_name(command: str) -> str:
    try:
        parts = shlex.split(command)
    except ValueError:
        return ""
    return Path(parts[0]).name if parts else ""
