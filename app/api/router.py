# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：router.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from fastapi import APIRouter, Depends

from app.api.api import common_router
from app.api.agent.api_agent import router as agent_router
from app.core.config import settings
from app.shared.server.common.base_depends import extract_request_id

api_router = APIRouter(dependencies=[Depends(extract_request_id)])

api_router.include_router(common_router, tags=["Common API"])

v1_router = APIRouter(prefix="/v1")
v1_router.include_router(agent_router, tags=["Agent API"])
api_router.include_router(v1_router, prefix=settings.server.API_PREFIX)
