# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：register_hook.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

import time
from datetime import datetime

from fastapi import FastAPI, Request

from app.utils.logger import logger


def register_hook(app: FastAPI) -> None:
    """注册请求响应 hook。"""

    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start_time = time.time()
        x_request_start = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        request.state.start_time = start_time

        response = await call_next(request)

        process_time = time.time() - start_time
        request_id = getattr(request.state, "request_id", "unknown")
        logger.info("request_id:%s -> process_time:%s", request_id, process_time)
        response.headers["X-Request-Id"] = str(request_id)
        response.headers["X-Request-Time"] = x_request_start
        response.headers["X-Response-Time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        response.headers["X-Process-Time"] = str(process_time)
        return response
