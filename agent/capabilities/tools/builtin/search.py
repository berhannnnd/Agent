from __future__ import annotations

from typing import Any

from agent.capabilities.tools.context import ToolRuntimeContext


GREP_SCHEMA = {
    "type": "object",
    "properties": {
        "pattern": {"type": "string", "description": "Regular expression to search for."},
        "path": {"type": "string", "description": "Workspace-relative file or directory path."},
        "max_results": {"type": "integer", "minimum": 1, "maximum": 1000},
        "case_sensitive": {"type": "boolean"},
    },
    "required": ["pattern"],
}


def grep(
    context: ToolRuntimeContext,
    pattern: str,
    path: str = ".",
    max_results: int = 100,
    case_sensitive: bool = True,
) -> dict[str, Any]:
    return context.sandbox_client.grep(
        pattern=pattern,
        path=path or ".",
        max_results=max_results,
        case_sensitive=case_sensitive,
    ).to_dict()
