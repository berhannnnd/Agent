# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：api.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from fastapi import APIRouter, Request

from gateway.api.handler import BaseHandler
from gateway.shared.server.common import resp

common_router = APIRouter()
handler = BaseHandler()


@common_router.get("/health")
async def health():
    return resp.ok(response=resp.Resp(data={"status": "ok"}))


@common_router.post("/callback")
async def callback(request: Request, data: dict):
    handler.log_request_data(request, data)
    return resp.ok(response=resp.Resp(data={"status": "ok"}))
