# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：logger.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# 2026/04/27   Deprecated: moved to app.core.logging
# =====================================================

import warnings

warnings.warn(
    "app.utils.logger is deprecated, use app.core.logging",
    DeprecationWarning,
    stacklevel=2,
)

from app.core.logging import *  # noqa: F401,F403
