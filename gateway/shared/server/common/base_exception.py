# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：base_exception.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# 2026/04/27   Deprecated: moved to gateway.core.exceptions
# =====================================================

import warnings

warnings.warn(
    "gateway.shared.server.common.base_exception is deprecated, use gateway.core.exceptions",
    DeprecationWarning,
    stacklevel=2,
)

from gateway.core.exceptions import *  # noqa: F401,F403
