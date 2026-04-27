# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：main.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

import warnings

warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

import uvicorn

from app.core.config import settings
from app.utils import utils
from app.utils.logger import logger


def create_app():
    from app.app import app

    return app


app = create_app()


if __name__ == "__main__":
    utils.print_info(settings, logger)

    uvicorn.run(
        "main:app" if settings.server.DEBUG else app,
        host=settings.server.HOST,
        port=settings.server.PORT,
        reload=settings.server.DEBUG and settings.server.WORKERS == 1,
        workers=settings.server.WORKERS,
        lifespan="on",
        log_config=utils.set_uvicorn_logger(settings.log.LOGGER_FORMAT),
    )
