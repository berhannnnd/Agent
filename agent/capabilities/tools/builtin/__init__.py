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
from agent.capabilities.tools.builtin.web import (
    WEB_EXTRACT_SCHEMA,
    WEB_MAP_SCHEMA,
    WEB_SEARCH_SCHEMA,
    web_extract,
    web_map,
    web_search,
)
from agent.capabilities.tools.context import ToolRuntimeContext
from agent.capabilities.tools.registry import ToolRegistry
from agent.capabilities.web import NullWebSearchProvider, WebSearchProvider


def register_builtin_tools(
    registry: ToolRegistry,
    context: ToolRuntimeContext,
    web_provider: WebSearchProvider | None = None,
) -> list[str]:
    active_web_provider = web_provider or NullWebSearchProvider()
    names = [
        "filesystem.read",
        "filesystem.list",
        "filesystem.write",
        "patch.apply",
        "search.grep",
        "web.search",
        "web.extract",
        "web.map",
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
        "web.search",
        "Search the web through the configured control-plane search provider and return cited sources.",
        WEB_SEARCH_SCHEMA,
        lambda query,
        topic="general",
        search_depth="basic",
        max_results=5,
        time_range="",
        include_domains=None,
        exclude_domains=None,
        country="",
        include_answer=False,
        include_raw_content=False,
        chunks_per_source=3: web_search(
            context,
            active_web_provider,
            query=query,
            topic=topic,
            search_depth=search_depth,
            max_results=max_results,
            time_range=time_range,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
            country=country,
            include_answer=include_answer,
            include_raw_content=include_raw_content,
            chunks_per_source=chunks_per_source,
        ),
        metadata={
            "risk": "medium",
            "requires_network": True,
            "external_disclosure": True,
            "provider": getattr(active_web_provider, "name", "none"),
        },
    )
    registry.register(
        "web.extract",
        "Extract clean content from specific URLs through the configured control-plane search provider.",
        WEB_EXTRACT_SCHEMA,
        lambda urls, query="", extract_depth="basic", format="markdown", chunks_per_source=3: web_extract(
            context,
            active_web_provider,
            urls=urls,
            query=query,
            extract_depth=extract_depth,
            format=format,
            chunks_per_source=chunks_per_source,
        ),
        metadata={
            "risk": "medium",
            "requires_network": True,
            "external_disclosure": True,
            "provider": getattr(active_web_provider, "name", "none"),
        },
    )
    registry.register(
        "web.map",
        "Discover URLs under a site through the configured control-plane search provider.",
        WEB_MAP_SCHEMA,
        lambda url, instructions="", max_depth=1, limit=50, include_domains=None, exclude_domains=None: web_map(
            context,
            active_web_provider,
            url=url,
            instructions=instructions,
            max_depth=max_depth,
            limit=limit,
            include_domains=include_domains,
            exclude_domains=exclude_domains,
        ),
        metadata={
            "risk": "high",
            "requires_network": True,
            "external_disclosure": True,
            "provider": getattr(active_web_provider, "name", "none"),
        },
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
    "WEB_EXTRACT_SCHEMA",
    "WEB_MAP_SCHEMA",
    "WEB_SEARCH_SCHEMA",
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
    "web_extract",
    "web_map",
    "web_search",
]
