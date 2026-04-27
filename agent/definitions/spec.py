from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, List, Optional

from agent.definitions.permissions import ToolPermissionSpec


@dataclass(frozen=True)
class AgentModelSpec:
    provider: Optional[str] = None
    model: Optional[str] = None
    base_url: Optional[str] = None
    api_key: Optional[str] = None

    @classmethod
    def from_dict(cls, payload: dict | None) -> "AgentModelSpec":
        if not payload:
            return cls()
        return cls(
            provider=payload.get("provider"),
            model=payload.get("model"),
            base_url=payload.get("base_url"),
            api_key=payload.get("api_key"),
        )

    def to_dict(self, include_secrets: bool = False) -> dict:
        payload = {
            "provider": self.provider,
            "model": self.model,
            "base_url": self.base_url,
        }
        if include_secrets:
            payload["api_key"] = self.api_key
        return {key: value for key, value in payload.items() if value not in (None, "")}


@dataclass(frozen=True)
class WorkspaceRef:
    tenant_id: str = ""
    user_id: str = ""
    agent_id: str = ""
    workspace_id: str = ""

    @classmethod
    def from_dict(cls, payload: dict | None) -> "WorkspaceRef":
        if not payload:
            return cls()
        return cls(
            tenant_id=str(payload.get("tenant_id") or ""),
            user_id=str(payload.get("user_id") or ""),
            agent_id=str(payload.get("agent_id") or ""),
            workspace_id=str(payload.get("workspace_id") or ""),
        )

    def to_dict(self) -> dict:
        return {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "agent_id": self.agent_id,
            "workspace_id": self.workspace_id,
        }


@dataclass(frozen=True)
class AgentSpec:
    agent_id: str = ""
    model: AgentModelSpec = field(default_factory=AgentModelSpec)
    workspace: WorkspaceRef = field(default_factory=WorkspaceRef)
    system_prompt: Optional[str] = None
    enabled_tools: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    permission_profile: str = ""
    tool_permissions: ToolPermissionSpec = field(default_factory=ToolPermissionSpec)
    memory_profile: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict | None) -> "AgentSpec":
        if not payload:
            return cls()
        return cls(
            agent_id=str(payload.get("agent_id") or ""),
            model=AgentModelSpec.from_dict(payload.get("model")),
            workspace=WorkspaceRef.from_dict(payload.get("workspace")),
            system_prompt=payload.get("system_prompt"),
            enabled_tools=list(payload["enabled_tools"]) if payload.get("enabled_tools") is not None else None,
            skills=list(payload["skills"]) if payload.get("skills") is not None else None,
            permission_profile=str(payload.get("permission_profile") or ""),
            tool_permissions=ToolPermissionSpec.from_dict(payload.get("tool_permissions")),
            memory_profile=str(payload.get("memory_profile") or ""),
            metadata=dict(payload.get("metadata") or {}),
        )

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
        permission_profile: str = "",
        approval_required_tools: Optional[List[str]] = None,
        denied_tools: Optional[List[str]] = None,
    ) -> "AgentSpec":
        tool_permissions = ToolPermissionSpec(
            mode=permission_profile or "auto",
            denied_tools=list(denied_tools or []),
            approval_required_tools=list(approval_required_tools or []),
        )
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
            permission_profile=permission_profile or "",
            tool_permissions=tool_permissions,
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

    def to_dict(self, include_secrets: bool = False) -> dict:
        payload = {
            "agent_id": self.agent_id,
            "model": self.model.to_dict(include_secrets=include_secrets),
            "workspace": self.workspace.to_dict(),
            "system_prompt": self.system_prompt,
            "enabled_tools": list(self.enabled_tools) if self.enabled_tools is not None else None,
            "skills": list(self.skills) if self.skills is not None else None,
            "permission_profile": self.permission_profile,
            "tool_permissions": self.tool_permissions.to_dict(),
            "memory_profile": self.memory_profile,
            "metadata": dict(self.metadata),
        }
        return {key: value for key, value in payload.items() if value not in (None, "", [], {})}
