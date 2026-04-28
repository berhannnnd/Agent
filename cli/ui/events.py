from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class UIEvent:
    """Renderer-neutral event used by CLI frontends."""

    type: str
    name: str = ""
    text: str = ""
    status: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

