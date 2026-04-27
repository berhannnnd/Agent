# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：logger.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

import logging
import os
import re
import sys
from logging.handlers import TimedRotatingFileHandler
from typing import Optional

from app.core.config import settings
from app.utils import utils


class RelativePathFormatter(logging.Formatter):
    """将日志文件名转换为项目相对路径。"""

    def format(self, record):
        record.filename = os.path.relpath(record.pathname, utils.ROOT_PATH).replace(os.sep, ".")
        return super().format(record)


def remove_ansi_escape(text: str) -> str:
    ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
    return ansi_escape.sub("", text)


def setup_logger(
    name: str,
    filename: Optional[str] = None,
    stdout: bool = True,
    level: str = "INFO",
    backup_count: int = 7,
) -> logging.Logger:
    if name in logging.Logger.manager.loggerDict:
        return logging.getLogger(name)

    logger = logging.getLogger(name)
    logger.setLevel(level.upper())
    logger.propagate = False

    formatter = RelativePathFormatter(settings.log.LOGGER_FORMAT, datefmt="%Y-%m-%d %H:%M:%S")
    writer_formatter = RelativePathFormatter(
        remove_ansi_escape(settings.log.LOGGER_FORMAT),
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if stdout:
        stream_handler = logging.StreamHandler(stream=sys.stdout)
        stream_handler.setFormatter(formatter)
        stream_handler.setLevel(level.upper())
        logger.addHandler(stream_handler)

    if filename:
        os.makedirs(os.path.dirname(filename), exist_ok=True)
        file_handler = TimedRotatingFileHandler(
            filename,
            when="D",
            interval=1,
            backupCount=backup_count,
            encoding="UTF-8",
        )
        file_handler.setFormatter(writer_formatter)
        file_handler.setLevel(level.upper())
        logger.addHandler(file_handler)

    return logger


logger = setup_logger(
    name=settings.server.PROJECT_NAME,
    filename=utils.abspath(f"{settings.log.LOG_PATH}/logger.log"),
    stdout=True,
    level=settings.log.LOG_LEVEL,
)
