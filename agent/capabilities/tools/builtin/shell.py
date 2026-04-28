from __future__ import annotations

from typing import Any

from agent.capabilities.tools.context import ToolRuntimeContext


RUN_COMMAND_SCHEMA = {
    "type": "object",
    "properties": {
        "command": {"type": "string", "description": "Shell command to run in the workspace."},
        "timeout_seconds": {"type": "number", "minimum": 1, "maximum": 120},
    },
    "required": ["command"],
}


async def run_command(
    context: ToolRuntimeContext,
    command: str,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    result = await context.sandbox_client.run_command(command, timeout_seconds=timeout_seconds)
    return result.to_dict()
