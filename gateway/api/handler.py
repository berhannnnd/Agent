# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：handler.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from typing import Union

from fastapi import Request
from pydantic import BaseModel

from gateway.core.logging import logger


class BaseHandler:
    """API Handler 基类。"""

    @staticmethod
    def log_request_data(request: Request, request_data: Union[BaseModel, dict]) -> None:
        if isinstance(request_data, BaseModel):
            request_data = request_data.model_dump()

        logger.info(
            "\n\n====================Request======================\n"
            "Host       : %s\n"
            "URL        : %s %s\n"
            "DATA       : %s\n",
            request.client.host if request.client else "unknown",
            request.method,
            request.url,
            request_data,
        )
