# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：base.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

import asyncio
from abc import ABC, abstractmethod
from typing import Any

from app.core.logging import logger


class BaseEngine(ABC):
    """引擎基类，负责生命周期和统一调用入口。"""

    def __init__(self, name: str):
        self.name = name
        self._initialized = False
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        async with self._lock:
            if self._initialized:
                return
            logger.info("初始化引擎: %s", self.name)
            await self._initialize()
            self._initialized = True

    async def shutdown(self) -> None:
        async with self._lock:
            if not self._initialized:
                return
            logger.info("关闭引擎: %s", self.name)
            await self._shutdown()
            self._initialized = False

    async def invoke(self, input_data: Any, **kwargs) -> Any:
        if not self._initialized:
            await self.initialize()
        return await self._invoke(input_data, **kwargs)

    @abstractmethod
    async def _initialize(self) -> None:
        raise NotImplementedError()

    async def _shutdown(self) -> None:
        return None

    @abstractmethod
    async def _invoke(self, input_data: Any, **kwargs) -> Any:
        raise NotImplementedError()
