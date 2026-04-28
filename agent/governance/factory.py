from __future__ import annotations

from agent.specs import AgentSpec
from agent.governance.permissions import (
    DenyAllToolPermissionPolicy,
    StaticToolPermissionPolicy,
    ToolPermissionPolicy,
)


def build_tool_permission_policy(spec: AgentSpec) -> ToolPermissionPolicy:
    permissions = spec.tool_permissions
    mode = permissions.normalized_mode()
    if mode == "deny":
        return DenyAllToolPermissionPolicy()
    return StaticToolPermissionPolicy(
        allowed_tools=permissions.allowed_tools,
        denied_tools=permissions.denied_tools,
        approval_required_tools=permissions.approval_required_tools,
        require_approval_for_all=mode == "ask",
    )
