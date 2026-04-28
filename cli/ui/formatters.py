from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def compact(value: Any, *, limit: int = 220) -> str:
    text = str(value)
    return text if len(text) <= limit else text[: limit - 1] + "…"


def compact_json(value: Any, *, limit: int = 220) -> str:
    if not value:
        return ""
    try:
        text = json.dumps(value, ensure_ascii=False)
    except TypeError:
        text = str(value)
    return compact(text, limit=limit)


def short_path(path: str) -> str:
    try:
        value = Path(path).expanduser()
        home = Path.home()
        return "~/%s" % value.relative_to(home) if value.is_relative_to(home) else str(value)
    except Exception:
        return str(path)


def short_endpoint(endpoint: str, *, limit: int = 36) -> str:
    value = str(endpoint or "")
    return value if len(value) <= limit else value[: limit - 1] + "…"


def endpoint_from_base_url(base_url: str) -> str:
    if not base_url:
        return ""
    parsed = urlparse(base_url)
    return parsed.netloc or base_url


def model_label(profile: str, protocol: str, model: str) -> str:
    base = "%s · %s" % (protocol, model)
    if not profile or profile in {protocol, model}:
        return base
    return "%s · %s" % (profile, base)


def tool_use_label(name: str, arguments: dict[str, Any]) -> str:
    path = str(arguments.get("path") or arguments.get("file") or arguments.get("target") or "")
    query = str(arguments.get("query") or arguments.get("pattern") or arguments.get("q") or "")
    command = str(arguments.get("command") or arguments.get("cmd") or "")
    url = str(arguments.get("url") or "")

    if name == "filesystem.list":
        return _with_subject("List", path or ".")
    if name == "filesystem.read":
        return _with_subject("Read", path or compact_json(arguments, limit=120))
    if name == "filesystem.write":
        return _with_subject("Write", path or compact_json(arguments, limit=120))
    if name == "patch.apply":
        return "Apply patch"
    if name == "search.grep":
        return _with_subject("Search", query or compact_json(arguments, limit=120))
    if name in {"shell.run", "test.run"}:
        return _with_subject("Run", command or compact_json(arguments, limit=120))
    if name in {"git.status", "git.diff"}:
        return name.replace(".", " ")
    if name in {"web.search", "web.map"}:
        return _with_subject("Search web", query or compact_json(arguments, limit=120))
    if name == "web.extract":
        return _with_subject("Extract", url or compact_json(arguments, limit=120))
    if name.startswith("browser."):
        return _with_subject(name.replace(".", " "), url or path or compact_json(arguments, limit=120))
    detail = compact_json(arguments, limit=120)
    return "%s %s" % (name, detail) if detail else name


def _with_subject(verb: str, subject: str) -> str:
    return "%s %s" % (verb, subject) if subject else verb
