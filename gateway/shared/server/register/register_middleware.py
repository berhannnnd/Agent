# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：register_middleware.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# 2026/04/27   Refactored: core logic moved to gateway.core.middleware
# =====================================================

from fastapi import FastAPI

from gateway.core.middleware import register_middleware as _register_middleware


def register_middleware(app: FastAPI) -> None:
    """注册跨域和鉴权中间件。"""
    _register_middleware(app)
