# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：exceptions.py
# @Date   ：2026/04/27 00:00
# @Author ：Zegen
#
# 2026/04/27   Create
# =====================================================


class ServerException(Exception):
    def __init__(self, errors):
        self.errors = errors


class AuthenticationException(ServerException):
    def __init__(self, errors: str = "Permission denied"):
        self.errors = errors
