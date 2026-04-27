# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：registry.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from typing import Dict, Generic, Optional, TypeVar

T = TypeVar("T")


class Registry(Dict[str, T], Generic[T]):
    """轻量级注册器。"""

    def register(self, name: str, item: Optional[T] = None):
        if item is not None:
            self[name] = item
            return item

        def decorator(fn):
            self[name] = fn()
            return fn

        return decorator
