from __future__ import annotations

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
    return context.sandbox_client.read_text(path, max_bytes=max_bytes).to_dict()


def list_dir(context: ToolRuntimeContext, path: str = ".") -> dict[str, Any]:
    return context.sandbox_client.list_dir(path or ".").to_dict()


def write_file(context: ToolRuntimeContext, path: str, content: str) -> dict[str, Any]:
    return context.sandbox_client.write_text(path, content).to_dict()
