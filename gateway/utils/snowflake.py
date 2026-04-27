# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：snowflake.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

import threading
import time


class SnowflakeWorker:
    """简化版雪花 ID 生成器。"""

    def __init__(self, worker_id: int = 1):
        self.worker_id = worker_id & 0x1F
        self.sequence = 0
        self.last_timestamp = -1
        self.lock = threading.Lock()

    @staticmethod
    def _timestamp() -> int:
        return int(time.time() * 1000)

    def get_id(self) -> int:
        with self.lock:
            timestamp = self._timestamp()
            if timestamp == self.last_timestamp:
                self.sequence = (self.sequence + 1) & 0xFFF
                if self.sequence == 0:
                    while timestamp <= self.last_timestamp:
                        timestamp = self._timestamp()
            else:
                self.sequence = 0

            self.last_timestamp = timestamp
            return ((timestamp - 1700000000000) << 17) | (self.worker_id << 12) | self.sequence


worker = SnowflakeWorker()
