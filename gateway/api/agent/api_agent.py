# !/usr/bin/env python
# -*- coding: utf-8 -*-
# =====================================================
# @File   ：api_agent.py
# @Date   ：2026/04/24 00:00
# @Author ：Zegen
#
# 2026/04/24   Create
# =====================================================

from __future__ import annotations

import asyncio
import inspect
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from agent.assembly import create_agent_session_async as _create_agent_session_async
from agent.config import AgentConfigError
from gateway.api.agent.schemas import AgentChatRequest
from gateway.core.config import settings
from gateway.shared.server.common import resp

router = APIRouter(prefix="/agent")

# 全局并发限制：同时处理的 agent 请求数
_agent_semaphore = asyncio.Semaphore(settings.agent.MAX_CONCURRENT_REQUESTS)


async def create_agent_session(**kwargs):
    return await _create_agent_session_async(settings, **kwargs)


@router.post("/chat")
async def chat(request_data: AgentChatRequest):
    async with _agent_semaphore:
        try:
            session = await _resolve_agent_session(
                spec=request_data.to_agent_spec(),
            )
            result = await session.send(request_data.message)
        except AgentConfigError as exc:
            return resp.fail(resp.Resp(code="400", detail=str(exc), http_status=400))
        return resp.ok(
            response=resp.Resp(
                data={
                    "content": result.content,
                    "messages": [message.to_dict() for message in result.messages],
                    "tool_results": [item.to_dict() for item in result.tool_results],
                    "events": [event.to_dict() for event in result.events],
                }
            )
        )


@router.post("/chat/stream")
async def chat_stream(request_data: AgentChatRequest):
    async def event_source():
        try:
            session = await _resolve_agent_session(
                spec=request_data.to_agent_spec(),
            )
            async for event in session.stream(request_data.message):
                yield _sse(event.type, event.to_dict())
        except Exception as exc:  # noqa: BLE001 - streams must report errors as events.
            yield _sse("error", {"type": "error", "payload": {"message": str(exc)}})

    # 流式请求的并发限制：获取 semaphore 后启动生成器
    await _agent_semaphore.acquire()

    async def _release_on_close():
        try:
            async for chunk in event_source():
                yield chunk
        finally:
            _agent_semaphore.release()

    return StreamingResponse(_release_on_close(), media_type="text/event-stream")


def _sse(event: str, data: dict) -> str:
    return "event: %s\ndata: %s\n\n" % (event, json.dumps(data, ensure_ascii=False))


async def _resolve_agent_session(**kwargs):
    session = create_agent_session(**kwargs)
    if inspect.isawaitable(session):
        return await session
    return session
