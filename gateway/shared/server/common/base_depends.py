# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：base_depends.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

import json

from fastapi import Request

from gateway.core.config import settings
from gateway.utils.snowflake import worker


async def extract_request_id(request: Request = None):
    """从请求中提取 request_id，不存在则自动生成。"""
    if request is None:
        return

    request_id = f"{settings.server.PROJECT_NAME}-{worker.get_id()}"
    content_type = request.headers.get("content-type", "")

    if request.method == "POST" and "application/json" in content_type:
        body_bytes = await request.body()
        try:
            body_data = json.loads(body_bytes)
            request_id = body_data.get("request_id", request_id)
        except Exception:
            pass
    elif request.method == "GET":
        request_id = request.query_params.get("request_id", request_id)

    request.state.request_id = request_id
