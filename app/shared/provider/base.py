# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：base.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from abc import ABC, abstractmethod
from typing import Any


class BaseProvider(ABC):
    """外部服务 Provider 基类。"""

    def __init__(self, name: str, provider: str):
        self.name = name
        self.provider = provider
        self.client_id = f"{name}_{provider}"

    @abstractmethod
    async def invoke(self, request: Any) -> Any:
        raise NotImplementedError()
