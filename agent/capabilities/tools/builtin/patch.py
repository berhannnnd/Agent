from __future__ import annotations

import difflib
from dataclasses import dataclass
from typing import Any

from agent.capabilities.tools.context import ToolRuntimeContext


PATCH_APPLY_SCHEMA = {
    "type": "object",
    "properties": {
        "edits": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Workspace-relative file path."},
                    "old_text": {"type": "string", "description": "Exact text to replace."},
                    "new_text": {"type": "string", "description": "Replacement text."},
                    "replace_all": {"type": "boolean", "description": "Replace all occurrences instead of requiring exactly one."},
                },
                "required": ["path", "old_text", "new_text"],
            },
        },
        "creates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Workspace-relative file path."},
                    "content": {"type": "string"},
                    "overwrite": {"type": "boolean", "description": "Allow replacing an existing file."},
                },
                "required": ["path", "content"],
            },
        },
        "dry_run": {"type": "boolean", "description": "Validate and return a diff without writing files."},
    },
}


@dataclass
class _PlannedFile:
    path: str
    before: str
    after: str
    action: str
    edit_count: int = 0


def apply_patch(
    context: ToolRuntimeContext,
    edits: list[dict[str, Any]] | None = None,
    creates: list[dict[str, Any]] | None = None,
    dry_run: bool = False,
) -> dict[str, Any]:
    edit_list = [dict(item) for item in (edits or []) if isinstance(item, dict)]
    create_list = [dict(item) for item in (creates or []) if isinstance(item, dict)]
    if not edit_list and not create_list:
        raise ValueError("patch.apply requires at least one edit or create operation")

    planned = _plan_patch(context, edit_list, create_list)
    diff = _combined_diff(planned)
    if not dry_run:
        for item in planned:
            context.sandbox_client.write_text(item.path, item.after)

    files = [
        {
            "path": item.path,
            "action": item.action,
            "edits": item.edit_count,
            "bytes": len(item.after.encode("utf-8")),
        }
        for item in planned
    ]
    return {
        "dry_run": bool(dry_run),
        "changed": not bool(dry_run),
        "files": files,
        "diff": _truncate(diff),
        "truncated": len(diff) > 20000,
    }


def _plan_patch(
    context: ToolRuntimeContext,
    edits: list[dict[str, Any]],
    creates: list[dict[str, Any]],
) -> list[_PlannedFile]:
    content_by_path: dict[str, str] = {}
    actions_by_path: dict[str, str] = {}
    edits_by_path: dict[str, int] = {}

    for operation in edits:
        path = _required_string(operation, "path")
        old_text = _required_string(operation, "old_text")
        new_text = str(operation.get("new_text") or "")
        if not old_text:
            raise ValueError("old_text cannot be empty for %s" % path)
        before = content_by_path.get(path)
        if before is None:
            before = context.sandbox_client.read_text(path, max_bytes=200000).content
        occurrences = before.count(old_text)
        if occurrences == 0:
            raise ValueError("old_text was not found in %s" % path)
        if occurrences > 1 and not bool(operation.get("replace_all")):
            raise ValueError("old_text matched %d times in %s; set replace_all to true or use a more specific edit" % (occurrences, path))
        count = occurrences if bool(operation.get("replace_all")) else 1
        content_by_path[path] = before.replace(old_text, new_text, count)
        actions_by_path.setdefault(path, "edit")
        edits_by_path[path] = edits_by_path.get(path, 0) + count

    for operation in creates:
        path = _required_string(operation, "path")
        content = str(operation.get("content") or "")
        overwrite = bool(operation.get("overwrite"))
        before = ""
        action = "create"
        try:
            before = context.sandbox_client.read_text(path, max_bytes=200000).content
            if not overwrite and path not in content_by_path:
                raise ValueError("file already exists: %s" % path)
            action = "overwrite"
        except FileNotFoundError:
            before = ""
        content_by_path[path] = content
        actions_by_path[path] = action
        edits_by_path[path] = edits_by_path.get(path, 0) + 1

    planned: list[_PlannedFile] = []
    for path, after in content_by_path.items():
        before = ""
        try:
            before = context.sandbox_client.read_text(path, max_bytes=200000).content
        except FileNotFoundError:
            before = ""
        if before == after:
            continue
        planned.append(
            _PlannedFile(
                path=path,
                before=before,
                after=after,
                action=actions_by_path.get(path, "edit"),
                edit_count=edits_by_path.get(path, 0),
            )
        )
    if not planned:
        raise ValueError("patch.apply produced no changes")
    return planned


def _combined_diff(files: list[_PlannedFile]) -> str:
    chunks: list[str] = []
    for item in files:
        chunks.extend(
            difflib.unified_diff(
                item.before.splitlines(keepends=True),
                item.after.splitlines(keepends=True),
                fromfile="a/%s" % item.path,
                tofile="b/%s" % item.path,
                lineterm="",
            )
        )
    return "\n".join(chunks)


def _required_string(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key) or "")
    if not value:
        raise ValueError("%s is required" % key)
    return value


def _truncate(text: str, limit: int = 20000) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n[truncated]"
