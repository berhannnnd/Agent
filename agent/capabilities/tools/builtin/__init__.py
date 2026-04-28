from __future__ import annotations

from agent.capabilities.tools.builtin.filesystem import (
    LIST_DIR_SCHEMA,
    READ_FILE_SCHEMA,
    WRITE_FILE_SCHEMA,
    list_dir,
    read_file,
    write_file,
)
from agent.capabilities.tools.builtin.shell import RUN_COMMAND_SCHEMA, run_command
from agent.capabilities.tools.context import ToolRuntimeContext
from agent.capabilities.tools.registry import ToolRegistry


def register_builtin_tools(registry: ToolRegistry, context: ToolRuntimeContext) -> list[str]:
    names = ["filesystem.read", "filesystem.list", "filesystem.write", "shell.run"]
    registry.register(
        "filesystem.read",
        "Read a UTF-8 text file from the current workspace.",
        READ_FILE_SCHEMA,
        lambda path, max_bytes=20000: read_file(context, path, max_bytes=max_bytes),
    )
    registry.register(
        "filesystem.list",
        "List files and directories inside the current workspace.",
        LIST_DIR_SCHEMA,
        lambda path=".": list_dir(context, path=path),
    )
    registry.register(
        "filesystem.write",
        "Write a UTF-8 text file inside the current workspace when the sandbox allows writes.",
        WRITE_FILE_SCHEMA,
        lambda path, content: write_file(context, path, content),
    )
    registry.register(
        "shell.run",
        "Run a shell command in the current workspace when the sandbox allows process execution.",
        RUN_COMMAND_SCHEMA,
        lambda command, timeout_seconds=20.0: run_command(context, command, timeout_seconds=timeout_seconds),
    )
    return names


__all__ = [
    "LIST_DIR_SCHEMA",
    "READ_FILE_SCHEMA",
    "RUN_COMMAND_SCHEMA",
    "WRITE_FILE_SCHEMA",
    "list_dir",
    "read_file",
    "register_builtin_tools",
    "run_command",
    "write_file",
]
