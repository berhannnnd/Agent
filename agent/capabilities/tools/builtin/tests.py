from __future__ import annotations

from typing import Any

from agent.capabilities.tools.context import ToolRuntimeContext


TEST_RUN_SCHEMA = {
    "type": "object",
    "properties": {
        "command": {"type": "string", "description": "Test command to run in the workspace."},
        "timeout_seconds": {"type": "number", "minimum": 1, "maximum": 600},
    },
}


async def run_tests(
    context: ToolRuntimeContext,
    command: str = "pytest",
    timeout_seconds: float = 120.0,
) -> dict[str, Any]:
    result = await context.sandbox_client.run_command(command or "pytest", timeout_seconds=timeout_seconds)
    return result.to_dict()
