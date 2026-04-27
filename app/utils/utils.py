# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：utils.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

import os
import time
from contextlib import contextmanager
from functools import wraps
from types import SimpleNamespace

ROOT_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))


def dict2obj(data):
    if isinstance(data, dict):
        return SimpleNamespace(**{k: dict2obj(v) for k, v in data.items()})
    return data


def obj2dict(obj) -> dict:
    result = {}
    for name in dir(obj):
        value = getattr(obj, name)
        if not name.startswith("__") and not callable(value) and not name.startswith("_"):
            result[name] = value
    return result


def abspath(relative_path: str) -> str:
    return os.path.abspath(os.path.join(ROOT_PATH, relative_path)).replace("\\", "/")


def ensure_dir(directory: str) -> None:
    os.makedirs(directory, exist_ok=True)


def set_uvicorn_logger(fmt: str):
    from uvicorn.config import LOGGING_CONFIG

    date_fmt = "%Y-%m-%d %H:%M:%S"
    LOGGING_CONFIG["formatters"]["access"]["datefmt"] = date_fmt
    LOGGING_CONFIG["formatters"]["access"]["fmt"] = fmt
    LOGGING_CONFIG["formatters"]["default"]["datefmt"] = date_fmt
    LOGGING_CONFIG["formatters"]["default"]["fmt"] = fmt
    return LOGGING_CONFIG


def print_info(settings, logger) -> None:
    print(settings.LOGO)
    logger.info("=======================================")
    settings.status(logger=logger)
    logger.info("=======================================")


@contextmanager
def timeblock(label: str):
    from app.core.logging import logger

    start = time.time()
    try:
        yield
    finally:
        logger.info("【%s】 cost time > %.4f", label, time.time() - start)


def runtime(_func=None, *, prefix: str = ""):
    if prefix:
        prefix = f"{prefix} - "

    def decorator(func):
        from app.core.logging import logger

        @wraps(func)
        def wrap(*args, **kwargs):
            start = time.perf_counter()
            ret = func(*args, **kwargs)
            logger.info("【%s%s】 runtime > %s", prefix, func.__name__, time.perf_counter() - start)
            return ret

        return wrap

    return decorator if _func is None else decorator(_func)
