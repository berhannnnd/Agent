# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：base_models.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from pydantic import BaseModel, ConfigDict


class AppSchema(BaseModel):
    """项目通用 Pydantic 基类。"""

    model_config = ConfigDict(extra="ignore")
