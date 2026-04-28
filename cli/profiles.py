from __future__ import annotations

import getpass
from copy import copy
from pathlib import Path
from typing import Optional

import typer

from agent.config import runtime_settings as settings

CODING_TOOLS = [
    "filesystem.read",
    "filesystem.list",
    "filesystem.write",
    "patch.apply",
    "search.grep",
    "git.status",
    "git.diff",
    "test.run",
    "shell.run",
]
CHAT_TOOLS = ["filesystem.read", "filesystem.list", "search.grep"]
BROWSER_TOOLS = [*CODING_TOOLS, "web.search", "web.extract", "browser.open", "browser.download"]
RISKY_TOOLS = ["filesystem.write", "patch.apply", "test.run", "shell.run", "browser.open", "browser.download"]
CODING_COMMANDS = "git,python,python3,pytest,make,node,npm,npx,bun"


def normalize_profile(profile: str) -> str:
    value = str(profile or "coding").strip().lower()
    if value not in {"coding", "chat", "browser"}:
        raise typer.BadParameter("profile must be coding, chat, or browser")
    return value


def workspace_path(profile: str, explicit: Optional[Path]) -> Optional[Path]:
    if explicit is not None:
        return explicit.expanduser().resolve()
    if profile in {"coding", "browser"}:
        return Path.cwd().resolve()
    return None


def enabled_tools(profile: str, tools: Optional[str]) -> list[str]:
    if tools:
        return [item.strip() for item in tools.split(",") if item.strip()]
    if profile == "browser":
        return list(BROWSER_TOOLS)
    if profile == "chat":
        return list(CHAT_TOOLS)
    return list(CODING_TOOLS)


def permission_settings(permission: str, profile: str) -> tuple[str, list[str]]:
    value = str(permission or "guarded").strip().lower()
    if value == "guarded":
        return "auto", list(RISKY_TOOLS if profile != "chat" else [])
    if value in {"auto", "ask", "deny"}:
        return value, []
    raise typer.BadParameter("permission must be guarded, auto, ask, or deny")


def settings_for_cli(profile: str, sandbox_provider: Optional[str]):
    runtime_settings = copy(settings)
    updates = {
        "SANDBOX_PROFILE": "browser" if profile == "browser" else ("coding" if profile == "coding" else "restricted"),
        "SANDBOX_ALLOWED_COMMANDS": _merge_csv(settings.agent.SANDBOX_ALLOWED_COMMANDS, CODING_COMMANDS),
    }
    if sandbox_provider:
        updates["SANDBOX_PROVIDER"] = sandbox_provider
    runtime_settings.agent = settings.agent.model_copy(update=updates)
    return runtime_settings


def system_prompt(base_prompt: Optional[str], profile: str, active_workspace: Optional[Path]) -> Optional[str]:
    if profile not in {"coding", "browser"}:
        return base_prompt
    guidance = (
        "You are running inside a local coding CLI. Treat the bound workspace as the project root. "
        "Before answering project-structure questions, inspect the workspace using a short reconnaissance pass: "
        "list the root, read project marker files such as README.md, pyproject.toml, package.json, makefile, and scan key directories with search.grep when useful. "
        "Do not infer architecture from a directory listing alone when readable project files are available. "
        "When asked to implement code, use filesystem.write or patch.apply for edits and run focused checks with test.run or shell.run. "
        "Keep all file paths inside the current workspace. "
        "Answer concisely with concrete file-backed observations and avoid offering unrelated follow-up menus."
    )
    if active_workspace is not None:
        guidance += " Current workspace: %s." % active_workspace
    return "%s\n\n%s" % (base_prompt, guidance) if base_prompt else guidance


def local_user_id() -> str:
    return getpass.getuser() or "local"


def _merge_csv(*values: str) -> str:
    result: list[str] = []
    seen = set()
    for value in values:
        for item in str(value or "").split(","):
            item = item.strip()
            if item and item not in seen:
                seen.add(item)
                result.append(item)
    return ",".join(result)
