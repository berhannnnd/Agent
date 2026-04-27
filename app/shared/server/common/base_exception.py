# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：base_exception.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# 2026/04/27   Deprecated: moved to app.core.exceptions
# =====================================================

import warnings

warnings.warn(
    "app.shared.server.common.base_exception is deprecated, use app.core.exceptions",
    DeprecationWarning,
    stacklevel=2,
)

from app.core.exceptions import *  # noqa: F401,F403
