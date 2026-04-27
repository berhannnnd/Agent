# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：launcher.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

import uvicorn


async def serve_http(**uvicorn_kwargs) -> None:
    """异步启动 uvicorn 服务。"""
    config = uvicorn.Config(**uvicorn_kwargs)
    server = uvicorn.Server(config)
    await server.serve()
