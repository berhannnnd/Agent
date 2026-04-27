# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：test_terminal_theme.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from app.core.config import settings
from app.core.logging import remove_ansi_escape
from app.utils.terminal import TermColors, colorize


def test_terminal_theme_copies_richinfo_palette():
    assert TermColors.WHITE == "\033[37m"
    assert TermColors.GRAY == "\033[90m"
    assert TermColors.MAGENTA == "\033[35m"
    assert TermColors.CYAN == "\033[36m"
    assert TermColors.GREEN == "\033[32m"
    assert colorize("msg", TermColors.GREEN) == "\033[32mmsg\033[0m"


def test_logger_format_uses_richinfo_terminal_colors():
    assert settings.log.LOGGER_FORMAT == (
        f"{TermColors.WHITE}[ {TermColors.GRAY}%(asctime)s {TermColors.WHITE}]"
        f"{TermColors.MAGENTA} %(levelname)-7s {TermColors.WHITE}| "
        f"{TermColors.CYAN}%(filename)s %(lineno)4d {TermColors.WHITE} - "
        f"{TermColors.GREEN}%(message)s{TermColors.WHITE}"
    )


def test_file_log_format_strips_terminal_colors():
    assert remove_ansi_escape(settings.log.LOGGER_FORMAT) == (
        "[ %(asctime)s ] %(levelname)-7s | "
        "%(filename)s %(lineno)4d  - %(message)s"
    )
