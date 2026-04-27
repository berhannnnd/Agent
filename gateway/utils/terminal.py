# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：terminal.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================


class TermColors:
    """Richinfo terminal color palette."""

    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"
    GRAY = "\033[90m"

    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"

    BOLD = "\033[1m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"

    RESET = "\033[0m"


def colorize(text: str, *styles: str) -> str:
    return "%s%s%s" % ("".join(styles), text, TermColors.RESET)
