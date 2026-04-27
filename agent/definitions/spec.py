from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, List, Optional


@dataclass(frozen=True)
class AgentModelSpec:
    provider: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None


@dataclass(frozen=True)
class WorkspaceRef:
    tenant_id: str = ""
    user_id: str = ""
    agent_id: str = ""
    workspace_id: str = ""


@dataclass(frozen=True)
class AgentSpec:
    agent_id: str = ""
    model: AgentModelSpec = field(default_factory=AgentModelSpec)
    workspace: WorkspaceRef = field(default_factory=WorkspaceRef)
    system_prompt: Optional[str] = None
    enabled_tools: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    permission_profile: str = ""
    memory_profile: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_overrides(
        cls,
        *,
        provider: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        system_prompt: Optional[str] = None,
        enabled_tools: Optional[List[str]] = None,
        tenant_id: str = "",
        user_id: str = "",
        agent_id: str = "",
        workspace_id: str = "",
        skills: Optional[List[str]] = None,
    ) -> "AgentSpec":
        return cls(
            agent_id=agent_id or "",
            model=AgentModelSpec(provider=provider, model=model, base_url=base_url, api_key=api_key),
            workspace=WorkspaceRef(
                tenant_id=tenant_id or "",
                user_id=user_id or "",
                agent_id=agent_id or "",
                workspace_id=workspace_id or "",
            ),
            system_prompt=system_prompt,
            enabled_tools=list(enabled_tools) if enabled_tools is not None else None,
            skills=list(skills) if skills is not None else None,
        )

    def with_workspace_defaults(self) -> "AgentSpec":
        if self.workspace.agent_id or not self.agent_id:
            return self
        return replace(
            self,
            workspace=WorkspaceRef(
                tenant_id=self.workspace.tenant_id,
                user_id=self.workspace.user_id,
                agent_id=self.agent_id,
                workspace_id=self.workspace.workspace_id,
            ),
        )
