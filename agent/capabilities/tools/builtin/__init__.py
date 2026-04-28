from __future__ import annotations

from agent.capabilities.tools.builtin.browser import (
    BROWSER_DOWNLOAD_SCHEMA,
    BROWSER_OPEN_SCHEMA,
    browser_download,
    browser_open,
)
from agent.capabilities.tools.builtin.filesystem import (
    LIST_DIR_SCHEMA,
    READ_FILE_SCHEMA,
    WRITE_FILE_SCHEMA,
    list_dir,
    read_file,
    write_file,
)
from agent.capabilities.tools.builtin.git import GIT_DIFF_SCHEMA, GIT_STATUS_SCHEMA, git_diff, git_status
from agent.capabilities.tools.builtin.patch import PATCH_APPLY_SCHEMA, apply_patch
from agent.capabilities.tools.builtin.search import GREP_SCHEMA, grep
from agent.capabilities.tools.builtin.shell import RUN_COMMAND_SCHEMA, run_command
from agent.capabilities.tools.builtin.tests import TEST_RUN_SCHEMA, run_tests
from agent.capabilities.tools.context import ToolRuntimeContext
from agent.capabilities.tools.registry import ToolRegistry


def register_builtin_tools(registry: ToolRegistry, context: ToolRuntimeContext) -> list[str]:
    names = [
        "filesystem.read",
        "filesystem.list",
        "filesystem.write",
        "patch.apply",
        "search.grep",
        "git.status",
        "git.diff",
        "test.run",
        "shell.run",
        "browser.open",
        "browser.download",
    ]
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
        metadata={"risk": "medium", "writes_files": True},
    )
    registry.register(
        "patch.apply",
        "Apply exact text edits or create text files inside the current workspace.",
        PATCH_APPLY_SCHEMA,
        lambda edits=None, creates=None, dry_run=False: apply_patch(
            context,
            edits=edits,
            creates=creates,
            dry_run=dry_run,
        ),
        metadata={"risk": "medium", "writes_files": True},
    )
    registry.register(
        "search.grep",
        "Search text files inside the current workspace with a regular expression.",
        GREP_SCHEMA,
        lambda pattern, path=".", max_results=100, case_sensitive=True: grep(
            context,
            pattern,
            path=path,
            max_results=max_results,
            case_sensitive=case_sensitive,
        ),
    )
    registry.register(
        "git.status",
        "Return git workspace status from inside the sandbox.",
        GIT_STATUS_SCHEMA,
        lambda short=True: git_status(context, short=short),
    )
    registry.register(
        "git.diff",
        "Return git diff output from inside the sandbox.",
        GIT_DIFF_SCHEMA,
        lambda path="", staged=False, max_bytes=20000: git_diff(
            context,
            path=path,
            staged=staged,
            max_bytes=max_bytes,
        ),
    )
    registry.register(
        "test.run",
        "Run a test command inside the sandbox.",
        TEST_RUN_SCHEMA,
        lambda command="pytest", timeout_seconds=120.0: run_tests(
            context,
            command=command,
            timeout_seconds=timeout_seconds,
        ),
        metadata={"risk": "high", "requires_process": True},
    )
    registry.register(
        "shell.run",
        "Run a shell command in the current workspace when the sandbox allows process execution.",
        RUN_COMMAND_SCHEMA,
        lambda command, timeout_seconds=20.0: run_command(context, command, timeout_seconds=timeout_seconds),
        metadata={"risk": "high", "requires_process": True},
    )
    registry.register(
        "browser.open",
        "Fetch an HTTP(S) page inside the sandbox and store it under workspace artifacts.",
        BROWSER_OPEN_SCHEMA,
        lambda url, output_path="artifacts/downloads/browser-open.html", max_bytes=200000: browser_open(
            context,
            url=url,
            output_path=output_path,
            max_bytes=max_bytes,
        ),
        metadata={"risk": "high", "requires_process": True, "requires_network": True, "writes_files": True},
    )
    registry.register(
        "browser.download",
        "Download an HTTP(S) URL inside the sandbox to a workspace-relative artifact path.",
        BROWSER_DOWNLOAD_SCHEMA,
        lambda url, path, max_bytes=20000000: browser_download(
            context,
            url=url,
            path=path,
            max_bytes=max_bytes,
        ),
        metadata={"risk": "high", "requires_process": True, "requires_network": True, "writes_files": True},
    )
    return names


__all__ = [
    "LIST_DIR_SCHEMA",
    "BROWSER_DOWNLOAD_SCHEMA",
    "BROWSER_OPEN_SCHEMA",
    "PATCH_APPLY_SCHEMA",
    "READ_FILE_SCHEMA",
    "GIT_DIFF_SCHEMA",
    "GIT_STATUS_SCHEMA",
    "GREP_SCHEMA",
    "RUN_COMMAND_SCHEMA",
    "TEST_RUN_SCHEMA",
    "WRITE_FILE_SCHEMA",
    "apply_patch",
    "browser_download",
    "browser_open",
    "git_diff",
    "git_status",
    "grep",
    "list_dir",
    "read_file",
    "register_builtin_tools",
    "run_command",
    "run_tests",
    "write_file",
]
