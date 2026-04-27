# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：schemas.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from typing import List, Optional

from pydantic import Field

from agent.definitions import AgentSpec
from gateway.shared.server.schemas.base_models import AppSchema


class AgentChatRequest(AppSchema):
    message: str = Field(..., description="User message")
    provider: Optional[str] = Field(None, description="Provider override")
    model: Optional[str] = Field(None, description="Model override")
    base_url: Optional[str] = Field(None, description="Base URL override")
    api_key: Optional[str] = Field(None, description="API key override")
    system_prompt: Optional[str] = Field(None, description="System prompt override")
    enabled_tools: Optional[List[str]] = Field(None, description="Enabled tool names")
    tenant_id: Optional[str] = Field(None, description="Tenant id for workspace resolution")
    user_id: Optional[str] = Field(None, description="User id for workspace resolution")
    agent_id: Optional[str] = Field(None, description="Agent id for workspace resolution")
    workspace_id: Optional[str] = Field(None, description="Workspace id for workspace resolution")

    def to_agent_spec(self) -> AgentSpec:
        return AgentSpec.from_overrides(
            provider=self.provider,
            model=self.model,
            base_url=self.base_url,
            api_key=self.api_key,
            system_prompt=self.system_prompt,
            enabled_tools=self.enabled_tools,
            tenant_id=self.tenant_id or "",
            user_id=self.user_id or "",
            agent_id=self.agent_id or "",
            workspace_id=self.workspace_id or "",
        )
