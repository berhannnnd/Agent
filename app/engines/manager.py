# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：manager.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from typing import Optional

from app.engines.base import BaseEngine
from app.engines.registry import engine_registry
from app.core.exceptions import ServerException
from app.core.logging import logger


class EngineManager:
    """统一引擎管理器。"""

    def __init__(self):
        self._engine_registry = engine_registry
        self._initialized = False

    def is_engine_supported(self, name: str) -> bool:
        return name in self._engine_registry

    def get_engine(self, name: str) -> BaseEngine:
        if not self.is_engine_supported(name):
            raise ServerException(f"引擎 {name} 未注册")
        return self._engine_registry[name]

    async def initialize_engines(self, names: Optional[list[str]] = None) -> None:
        logger.info("开始初始化引擎...")
        items = self._engine_registry.items()
        if names is not None:
            items = [(name, self._engine_registry[name]) for name in names if name in self._engine_registry]

        for name, engine in items:
            logger.info("初始化引擎: %s", name)
            await engine.initialize()

        self._initialized = True
        logger.info("引擎初始化完成")

    async def shutdown_engines(self) -> None:
        for name, engine in reversed(list(self._engine_registry.items())):
            logger.info("关闭引擎: %s", name)
            await engine.shutdown()
        self._initialized = False


engine_manager = EngineManager()
