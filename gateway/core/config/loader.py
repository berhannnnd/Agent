from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from gateway.core.config._constants import ROOT_PATH

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - only used on Python 3.10.
    import tomli as tomllib


DEFAULT_CONFIG_FILE = Path(ROOT_PATH) / "config" / "defaults.toml"
LOCAL_CONFIG_FILE = Path(ROOT_PATH) / "config" / "local.toml"


def config_value(section: str, key: str, default: Any) -> Any:
    payload = config_section(section)
    value = payload.get(key.lower())
    if value is None:
        value = payload.get(key.upper())
    return default if value is None else value


def config_section(section: str) -> dict[str, Any]:
    node: Any = project_config()
    for part in section.split("."):
        if not isinstance(node, dict):
            return {}
        node = node.get(part) or node.get(part.lower()) or node.get(part.upper()) or {}
    if not isinstance(node, dict):
        return {}
    return _normalize_keys(node)


@lru_cache(maxsize=1)
def project_config() -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for path in _config_paths():
        _deep_merge(payload, _load_toml(path))
    return payload


def _config_paths() -> list[Path]:
    defaults = Path(os.environ.get("AGENTS_DEFAULT_CONFIG", DEFAULT_CONFIG_FILE))
    local = Path(os.environ.get("AGENTS_LOCAL_CONFIG", LOCAL_CONFIG_FILE))
    return [defaults, local]


def _load_toml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _deep_merge(base: dict[str, Any], update: dict[str, Any]) -> None:
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], value)
            continue
        base[key] = value


def _normalize_keys(payload: dict[str, Any]) -> dict[str, Any]:
    return {str(key).lower(): value for key, value in payload.items()}
