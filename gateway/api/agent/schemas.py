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

from gateway.shared.server.schemas.base_models import AppSchema


class AgentChatRequest(AppSchema):
    message: str = Field(..., description="User message")
    provider: Optional[str] = Field(None, description="Provider override")
    model: Optional[str] = Field(None, description="Model override")
    base_url: Optional[str] = Field(None, description="Base URL override")
    api_key: Optional[str] = Field(None, description="API key override")
    system_prompt: Optional[str] = Field(None, description="System prompt override")
    enabled_tools: Optional[List[str]] = Field(None, description="Enabled tool names")
