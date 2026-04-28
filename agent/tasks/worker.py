from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import List, Optional, Protocol

from agent.tasks.runner import TaskExecutionResult, TaskRunner


@dataclass(frozen=True)
class TaskQueueItem:
    task_id: str
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, str] = field(default_factory=dict)


class TaskQueue(Protocol):
    async def enqueue(self, task_id: str, metadata: dict[str, str] | None = None) -> TaskQueueItem:
        raise NotImplementedError()

    async def dequeue(self) -> Optional[TaskQueueItem]:
        raise NotImplementedError()

    async def size(self) -> int:
        raise NotImplementedError()


class InMemoryTaskQueue:
    def __init__(self):
        self._items: List[TaskQueueItem] = []

    async def enqueue(self, task_id: str, metadata: dict[str, str] | None = None) -> TaskQueueItem:
        item = TaskQueueItem(task_id=task_id, metadata=dict(metadata or {}))
        self._items.append(item)
        return item

    async def dequeue(self) -> Optional[TaskQueueItem]:
        if not self._items:
            return None
        return self._items.pop(0)

    async def size(self) -> int:
        return len(self._items)


class TaskWorker:
    def __init__(self, queue: TaskQueue, runner: TaskRunner):
        self.queue = queue
        self.runner = runner

    async def run_next(self) -> Optional[TaskExecutionResult]:
        item = await self.queue.dequeue()
        if item is None:
            return None
        return await self.runner.run_task(item.task_id)

    async def run_until_empty(self, limit: int | None = None) -> List[TaskExecutionResult]:
        results: List[TaskExecutionResult] = []
        while limit is None or len(results) < limit:
            result = await self.run_next()
            if result is None:
                break
            results.append(result)
        return results
