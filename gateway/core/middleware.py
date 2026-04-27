# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：middleware.py
# @Date   ：2026/04/27 00:00
# @Author ：Zegen
#
# 2026/04/27   Create
# =====================================================

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from starlette.middleware.cors import CORSMiddleware

from gateway.core.config import settings
from gateway.core.logging import logger
from gateway.shared.server.common.base_resp import Unauthorized


def register_middleware(app: FastAPI) -> None:
    """注册跨域和鉴权中间件。"""
    if settings.server.BACKEND_CORS_ORIGINS:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=[str(origin) for origin in settings.server.BACKEND_CORS_ORIGINS],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    if settings.server.ACCESS_TOKEN:
        @app.middleware("http")
        async def authentication(request: Request, call_next):
            if request.method == "OPTIONS":
                return await call_next(request)

            if not request.url.path.startswith(settings.server.API_PREFIX):
                return await call_next(request)

            authorization = request.headers.get("Authorization")
            if authorization != f"Bearer {settings.server.ACCESS_TOKEN}":
                response_data = Unauthorized.model_copy(deep=True)
                response_data.message = "Token is invalid"
                logger.error("Token is invalid: %s", authorization)
                return JSONResponse(
                    content=jsonable_encoder(response_data.resp_dict),
                    status_code=response_data.http_status,
                )

            return await call_next(request)
