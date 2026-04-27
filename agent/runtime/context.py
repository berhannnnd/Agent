from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class RuntimeConfig:
    provider: str
    model: str
    enabled_tools: List[str] = field(default_factory=list)
    max_tool_iterations: int = 8

    def tool_names(self) -> List[str] | None:
        return list(self.enabled_tools) if self.enabled_tools else None
