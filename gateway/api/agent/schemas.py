# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：schemas.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from typing import Dict, List, Optional

from pydantic import Field

from agent.specs import AgentSpec
from gateway.shared.server.schemas.base_models import AppSchema


class AgentChatRequest(AppSchema):
    message: str = Field(..., description="User message")
    protocol: Optional[str] = Field(None, description="Model protocol override")
    model: Optional[str] = Field(None, description="Model override")
    base_url: Optional[str] = Field(None, description="Base URL override")
    api_key: Optional[str] = Field(None, description="API key override")
    system_prompt: Optional[str] = Field(None, description="System prompt override")
    enabled_tools: Optional[List[str]] = Field(None, description="Enabled tool names")
    permission_profile: Optional[str] = Field(None, description="Tool permission mode: auto, ask, or deny")
    approval_required_tools: Optional[List[str]] = Field(None, description="Tool names that require approval")
    denied_tools: Optional[List[str]] = Field(None, description="Tool names that are always denied")
    tenant_id: Optional[str] = Field(None, description="Tenant id for workspace resolution")
    user_id: Optional[str] = Field(None, description="User id for workspace resolution")
    agent_id: Optional[str] = Field(None, description="Agent id for workspace resolution")
    workspace_id: Optional[str] = Field(None, description="Workspace id for workspace resolution")

    def to_agent_spec(self) -> AgentSpec:
        return AgentSpec.from_overrides(
            protocol=self.protocol,
            model=self.model,
            base_url=self.base_url,
            api_key=self.api_key,
            system_prompt=self.system_prompt,
            enabled_tools=self.enabled_tools,
            tenant_id=self.tenant_id or "",
            user_id=self.user_id or "",
            agent_id=self.agent_id or "",
            workspace_id=self.workspace_id or "",
            permission_profile=self.permission_profile or "",
            approval_required_tools=self.approval_required_tools,
            denied_tools=self.denied_tools,
        )


class RunApprovalRequest(AppSchema):
    approved: bool = Field(True, description="Whether the selected pending tool calls are approved")
    decision: Optional[str] = Field(None, description="Approval decision: allow_once, allow_for_run, or deny")
    tool_call_ids: Optional[List[str]] = Field(None, description="Approval ids to decide; empty means all pending calls")
    approvals: Optional[Dict[str, bool]] = Field(None, description="Explicit approval id to decision map")
    decisions: Optional[Dict[str, str]] = Field(None, description="Explicit approval id to approval decision map")
    reason: Optional[str] = Field(None, description="Optional audit reason")


class AgentTaskCreateRequest(AgentChatRequest):
    title: Optional[str] = Field(None, description="Task title; defaults to the message prefix")
    metadata: Optional[Dict[str, str]] = Field(None, description="Task metadata")
