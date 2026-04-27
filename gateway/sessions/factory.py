from __future__ import annotations

from pathlib import Path
from typing import Any

from agent.runs import InMemoryRunStore, LocalFileRunStore, RunStore


def create_run_store(settings: Any) -> RunStore:
    store_kind = str(getattr(settings.agent, "RUN_STORE", "memory") or "memory").strip().lower()
    if store_kind == "file":
        configured_root = Path(str(getattr(settings.agent, "RUN_ROOT", ".agents/runs")))
        root = configured_root if configured_root.is_absolute() else Path(settings.server.ROOT_PATH) / configured_root
        return LocalFileRunStore(root)
    if store_kind == "memory":
        return InMemoryRunStore()
    raise ValueError("unsupported AGENT_RUN_STORE: %s" % store_kind)
