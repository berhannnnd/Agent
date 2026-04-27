import asyncio
import random
from dataclasses import dataclass

from agent.providers.errors import (
    ModelClientError,
    ModelRateLimitError,
    ModelServerError,
    ModelTimeoutError,
)


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 3
    base_delay: float = 1.0
    retry_429: bool = True
    retry_5xx: bool = True
    retry_timeout: bool = True


def _should_retry(err: ModelClientError, attempt: int, policy: RetryPolicy) -> bool:
    if attempt >= policy.max_attempts:
        return False
    if isinstance(err, ModelRateLimitError) and policy.retry_429:
        return True
    if isinstance(err, ModelServerError) and policy.retry_5xx:
        return True
    if isinstance(err, ModelTimeoutError) and policy.retry_timeout:
        return True
    return False


def _backoff(base_delay: float, attempt: int) -> float:
    """指数退避 + jitter(0.9~1.1)。attempt 从 1 开始计数。"""
    if attempt <= 1:
        return base_delay
    exp = 2 ** (attempt - 1)
    raw = base_delay * exp
    jitter = random.uniform(0.9, 1.1)
    return raw * jitter


async def _run_with_retry(policy: RetryPolicy, op):
    """运行异步操作，在可重试错误时按策略重试。"""
    last_err = None
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return await op()
        except ModelClientError as err:
            last_err = err
            if not _should_retry(err, attempt, policy):
                raise
            delay = _backoff(policy.base_delay, attempt)
            await asyncio.sleep(delay)
    raise last_err
