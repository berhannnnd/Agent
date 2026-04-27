# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：app.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from contextlib import asynccontextmanager

from fastapi import FastAPI

import gateway.engines.registry  # noqa: F401
from gateway.api.router import api_router
from gateway.core.config import settings
from gateway.engines.manager import engine_manager
from gateway.shared.server.register import register_exception, register_hook, register_middleware
from gateway.core.logging import logger
from gateway.static_ui import register_web_ui


@asynccontextmanager
async def lifespan(server: FastAPI):
    """应用生命周期管理。"""
    if settings.server.ENABLE_ENGINES:
        await engine_manager.initialize_engines()

    setattr(server, "logger", logger)
    yield

    await engine_manager.shutdown_engines()
    logger.info("Application shutdown complete.")


def create_app() -> FastAPI:
    """生成 FastAPI 应用对象。"""
    application = FastAPI(
        debug=settings.server.DEBUG,
        title=settings.server.PROJECT_NAME,
        lifespan=lifespan,
        openapi_url="/openapi.json" if settings.server.ENABLE_SWAGGER_DOC else None,
        docs_url="/docs" if settings.server.ENABLE_SWAGGER_DOC else None,
        redoc_url="/redoc" if settings.server.ENABLE_SWAGGER_DOC else None,
        routes=api_router.routes,
    )

    register_web_ui(application)
    register_middleware(application)
    register_exception(application)
    register_hook(application)
    return application


app = create_app()
