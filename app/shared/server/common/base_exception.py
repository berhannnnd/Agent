# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：base_exception.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from app.shared.server.common.base_resp import ServerError, Unauthorized


class ServerException(Exception):
    def __init__(self, errors):
        self.errors = errors
        self.resp = ServerError.model_copy(deep=True)


class AuthenticationException(ServerException):
    def __init__(self, errors: str = "Permission denied"):
        self.errors = errors
        self.resp = Unauthorized.model_copy(deep=True)
