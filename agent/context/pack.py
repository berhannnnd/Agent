from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, List


class ContextLayer(str, Enum):
    SYSTEM = "system"
    RUNTIME_POLICY = "runtime_policy"
    PROJECT_INSTRUCTIONS = "project_instructions"
    SKILLS = "skills"
    MEMORY = "memory"
    TOOL_HINTS = "tool_hints"
    TASK_CONTEXT = "task_context"


class ContextScope(str, Enum):
    GLOBAL = "global"
    PROJECT = "project"
    SESSION = "session"
    TURN = "turn"
    TOOL = "tool"


@dataclass(frozen=True)
class ContextFragment:
    id: str
    layer: ContextLayer
    text: str
    source: str
    priority: int = 0
    scope: ContextScope = ContextScope.SESSION
    enabled: bool = True
    tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def token_count(self) -> int:
        if self.tokens is not None:
            return self.tokens
        return _estimate_tokens(self.text)


@dataclass(frozen=True)
class ContextTraceItem:
    id: str
    layer: ContextLayer
    source: str
    tokens: int
    included: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": self.id,
            "layer": self.layer.value,
            "source": self.source,
            "tokens": self.tokens,
            "included": self.included,
        }
        if self.reason:
            payload["reason"] = self.reason
        return payload


@dataclass(frozen=True)
class CompiledContext:
    system_text: str
    trace: List[ContextTraceItem]
    token_estimate: int


@dataclass(frozen=True)
class ContextPack:
    fragments: List[ContextFragment] = field(default_factory=list)

    @classmethod
    def of(cls, fragments: Iterable[ContextFragment]) -> "ContextPack":
        return cls([fragment for fragment in fragments if fragment.enabled and fragment.text.strip()])

    def add(self, fragment: ContextFragment) -> "ContextPack":
        return ContextPack(self.fragments + [fragment])

    def extend(self, fragments: Iterable[ContextFragment]) -> "ContextPack":
        return ContextPack.of([*self.fragments, *fragments])


def _estimate_tokens(text: str) -> int:
    return max(1, len(text.encode("utf-8")) // 4)
