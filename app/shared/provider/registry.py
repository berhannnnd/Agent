# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：registry.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from app.shared.provider.base import BaseProvider
from app.utils.registry import Registry


provider_registry: Registry[BaseProvider] = Registry()
