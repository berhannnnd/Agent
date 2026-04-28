from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Protocol

from agent.specs import AgentSpec


class AgentRoleKind(str, Enum):
    PLANNER = "planner"
    WORKER = "worker"
    REVIEWER = "reviewer"
    ROUTER = "router"
    CUSTOM = "custom"


@dataclass(frozen=True)
class AgentRole:
    role_id: str
    kind: AgentRoleKind
    spec: AgentSpec
    description: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class HandoffDecision:
    target_role_id: str
    reason: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


class AgentRouter(Protocol):
    def route(self, task_input: str, roles: List[AgentRole]) -> HandoffDecision:
        raise NotImplementedError()


class StaticAgentRouter:
    def __init__(self, default_role_id: str = ""):
        self.default_role_id = default_role_id

    def route(self, task_input: str, roles: List[AgentRole]) -> HandoffDecision:
        if not roles:
            raise ValueError("no agent roles available")
        if self.default_role_id:
            for role in roles:
                if role.role_id == self.default_role_id:
                    return HandoffDecision(role.role_id, reason="static default")
        return HandoffDecision(roles[0].role_id, reason="first available role")
