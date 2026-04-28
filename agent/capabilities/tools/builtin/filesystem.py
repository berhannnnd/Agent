from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.capabilities.tools.context import ToolRuntimeContext


READ_FILE_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Workspace-relative file path."},
        "max_bytes": {"type": "integer", "minimum": 1, "maximum": 200000},
    },
    "required": ["path"],
}

LIST_DIR_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Workspace-relative directory path."},
    },
}

WRITE_FILE_SCHEMA = {
    "type": "object",
    "properties": {
        "path": {"type": "string", "description": "Workspace-relative file path."},
        "content": {"type": "string"},
    },
    "required": ["path", "content"],
}


def read_file(context: ToolRuntimeContext, path: str, max_bytes: int = 20000) -> dict[str, Any]:
    decision = context.sandbox.authorize_file_read(path)
    if not decision.allowed:
        raise PermissionError(decision.reason)
    resolved = context.sandbox.resolve_workspace_path(path)
    if not resolved.is_file():
        raise FileNotFoundError(str(path))
    limit = max(1, min(int(max_bytes or 20000), 200000))
    data = resolved.read_bytes()[:limit]
    return {
        "path": _relative_path(context, resolved),
        "content": data.decode("utf-8", errors="replace"),
        "truncated": resolved.stat().st_size > limit,
    }


def list_dir(context: ToolRuntimeContext, path: str = ".") -> dict[str, Any]:
    decision = context.sandbox.authorize_file_read(path)
    if not decision.allowed:
        raise PermissionError(decision.reason)
    resolved = context.sandbox.resolve_workspace_path(path or ".")
    if not resolved.is_dir():
        raise NotADirectoryError(str(path))
    entries = []
    for child in sorted(resolved.iterdir(), key=lambda item: item.name):
        entries.append(
            {
                "name": child.name,
                "path": _relative_path(context, child),
                "type": "directory" if child.is_dir() else "file",
            }
        )
    return {"path": _relative_path(context, resolved), "entries": entries}


def write_file(context: ToolRuntimeContext, path: str, content: str) -> dict[str, Any]:
    decision = context.sandbox.authorize_file_write(path)
    if not decision.allowed:
        raise PermissionError(decision.reason)
    resolved = context.sandbox.resolve_workspace_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(str(content), encoding="utf-8")
    return {"path": _relative_path(context, resolved), "bytes": len(str(content).encode("utf-8"))}


def _relative_path(context: ToolRuntimeContext, path: Path) -> str:
    return str(path.resolve().relative_to(context.workspace.path.resolve()))
