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
import json

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from agent.assembly import create_agent_session_async as _create_agent_session_async
from agent.config import AgentConfigError
from agent.schema import RuntimeEvent
from gateway.api.agent.schemas import AgentChatRequest
from gateway.core.config import settings
from gateway.sessions import GatewayRunService, run_created_event
from gateway.shared.server.common import resp

router = APIRouter(prefix="/agent")

# 全局并发限制：同时处理的 agent 请求数
_agent_semaphore = asyncio.Semaphore(settings.agent.MAX_CONCURRENT_REQUESTS)
run_service = GatewayRunService()


async def create_agent_session(**kwargs):
    return await _create_agent_session_async(settings, **kwargs)


@router.post("/chat")
async def chat(request_data: AgentChatRequest):
    async with _agent_semaphore:
        spec = request_data.to_agent_spec()
        run = await run_service.start(spec)
        try:
            session = await create_agent_session(spec=spec)
            result = await session.send(request_data.message, run_id=run.run_id)
            await run_service.record_events(run.run_id, result.events)
            await run_service.finish(run.run_id, _result_error(result.events))
        except AgentConfigError as exc:
            await _fail_run(run.run_id, "config", str(exc))
            return resp.fail(resp.Resp(code="400", detail={"run_id": run.run_id, "message": str(exc)}, http_status=400))
        except Exception as exc:  # noqa: BLE001 - gateway must persist failed run state before returning.
            await _fail_run(run.run_id, "runtime", str(exc))
            return resp.fail(resp.Resp(code="500", detail={"run_id": run.run_id, "message": str(exc)}, http_status=500))
        return resp.ok(
            response=resp.Resp(
                data={
                    "run_id": run.run_id,
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
        spec = request_data.to_agent_spec()
        run = None
        try:
            run = await run_service.start(spec)
            yield _sse("run_created", run_created_event(run.run_id).to_dict())
            session = await create_agent_session(spec=spec)
            stream_error = ""
            async for event in session.stream(request_data.message, run_id=run.run_id):
                await run_service.record_event(run.run_id, event)
                if event.type == "done":
                    stream_error = str(event.payload.get("error") or "")
                yield _sse(event.type, event.to_dict())
            await run_service.finish(run.run_id, stream_error)
        except Exception as exc:  # noqa: BLE001 - streams must report errors as events.
            if run is not None:
                await _fail_run(run.run_id, "runtime", str(exc))
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


def _result_error(events) -> str:
    for event in events:
        if event.type == "error":
            return str(event.payload.get("message") or "runtime error")
    return ""


async def _fail_run(run_id: str, kind: str, message: str) -> None:
    await run_service.record_event(run_id, RuntimeEvent(type="error", name=kind, payload={"message": message}))
    await run_service.finish(run_id, message)
