from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class TenantRef:
    id: str = "default"


@dataclass(frozen=True)
class UserRef:
    id: str = "anonymous"


@dataclass(frozen=True)
class AgentRef:
    id: str = "default"


@dataclass(frozen=True)
class Principal:
    tenant: TenantRef = field(default_factory=TenantRef)
    user: UserRef = field(default_factory=UserRef)
    roles: List[str] = field(default_factory=list)

    @classmethod
    def anonymous(cls) -> "Principal":
        return cls()
