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
from agent.security import ApprovalAuditRecord
from gateway.api.agent.schemas import AgentChatRequest, RunApprovalRequest
from gateway.core.config import settings
from gateway.sessions import (
    GatewayRunService,
    create_approval_audit_store,
    create_checkpoint_store,
    create_run_store,
    run_created_event,
)
from gateway.shared.server.common import resp

router = APIRouter(prefix="/agent")

# 全局并发限制：同时处理的 agent 请求数
_agent_semaphore = asyncio.Semaphore(settings.agent.MAX_CONCURRENT_REQUESTS)
run_service = GatewayRunService(create_run_store(settings))
checkpoint_store = create_checkpoint_store(settings)
approval_audit_store = create_approval_audit_store(settings)


async def create_agent_session(**kwargs):
    return await _create_agent_session_async(settings, checkpoint_store=checkpoint_store, **kwargs)


@router.post("/chat")
async def chat(request_data: AgentChatRequest):
    async with _agent_semaphore:
        spec = request_data.to_agent_spec()
        run = await run_service.start(spec)
        try:
            session = await create_agent_session(spec=spec)
            result = await session.send(request_data.message, run_id=run.run_id)
            await run_service.record_events(run.run_id, result.events)
            await _complete_or_pause(run.run_id, result.status, result.events)
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
                    "status": result.status,
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
            approval_required = False
            async for event in session.stream(request_data.message, run_id=run.run_id):
                await run_service.record_event(run.run_id, event)
                if event.type == "done":
                    stream_error = str(event.payload.get("error") or "")
                    approval_required = event.payload.get("status") == "awaiting_approval"
                if event.type == "tool_approval_required":
                    approval_required = True
                yield _sse(event.type, event.to_dict())
            if approval_required:
                await run_service.pause_for_approval(run.run_id)
            else:
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


@router.get("/runs/{run_id}")
async def get_run(run_id: str):
    record = await run_service.store.load_run(run_id)
    if record is None:
        return resp.fail(resp.Resp(code="404", detail="run not found: %s" % run_id, http_status=404))
    return resp.ok(response=resp.Resp(data=record.to_dict()))


@router.post("/runs/{run_id}/approval")
async def approve_run_tools(run_id: str, request_data: RunApprovalRequest):
    async with _agent_semaphore:
        record = await run_service.store.load_run(run_id)
        if record is None:
            return resp.fail(resp.Resp(code="404", detail="run not found: %s" % run_id, http_status=404))
        checkpoint = await checkpoint_store.load(run_id)
        if checkpoint is None or not checkpoint.pending_tool_calls:
            return resp.fail(resp.Resp(code="409", detail="run is not waiting for tool approval", http_status=409))

        approvals = _approval_map(request_data, checkpoint.pending_tool_calls)
        try:
            await _record_approval_audit(run_id, request_data, checkpoint.pending_tool_calls, approvals)
            await run_service.mark_running(run_id)
            session = await create_agent_session(spec=record.to_agent_spec())
            result = await session.resume(run_id, approvals=approvals)
            new_events = _new_runtime_events(record.events, result.events)
            await run_service.record_events(run_id, new_events)
            await _complete_or_pause(run_id, result.status, result.events)
        except AgentConfigError as exc:
            await _fail_run(run_id, "config", str(exc))
            return resp.fail(resp.Resp(code="400", detail={"run_id": run_id, "message": str(exc)}, http_status=400))
        except Exception as exc:  # noqa: BLE001 - approval resume must persist failed run state.
            await _fail_run(run_id, "runtime", str(exc))
            return resp.fail(resp.Resp(code="500", detail={"run_id": run_id, "message": str(exc)}, http_status=500))
        return resp.ok(
            response=resp.Resp(
                data={
                    "run_id": run_id,
                    "status": result.status,
                    "content": result.content,
                    "messages": [message.to_dict() for message in result.messages],
                    "tool_results": [item.to_dict() for item in result.tool_results],
                    "events": [event.to_dict() for event in new_events],
                }
            )
        )


def _sse(event: str, data: dict) -> str:
    return "event: %s\ndata: %s\n\n" % (event, json.dumps(data, ensure_ascii=False))


def _result_error(events) -> str:
    for event in events:
        if event.type == "error":
            return str(event.payload.get("message") or "runtime error")
    return ""


async def _complete_or_pause(run_id: str, status: str, events) -> None:
    if status == "awaiting_approval" or any(event.type == "tool_approval_required" for event in events):
        await run_service.pause_for_approval(run_id)
        return
    await run_service.finish(run_id, _result_error(events))


async def _fail_run(run_id: str, kind: str, message: str) -> None:
    await run_service.record_event(run_id, RuntimeEvent(type="error", name=kind, payload={"message": message}))
    await run_service.finish(run_id, message)


def _approval_map(request_data: RunApprovalRequest, pending_calls) -> dict[str, bool]:
    if request_data.approvals:
        return {str(key): bool(value) for key, value in request_data.approvals.items()}
    pending_ids = [call.id or call.name for call in pending_calls]
    selected = request_data.tool_call_ids or pending_ids
    return {str(item): bool(request_data.approved) for item in selected}


def _new_runtime_events(record_events, result_events) -> list[RuntimeEvent]:
    recorded_runtime_events = [event for event in record_events if event.type != "run_created"]
    return list(result_events)[len(recorded_runtime_events):]


async def _record_approval_audit(run_id: str, request_data: RunApprovalRequest, pending_calls, approvals: dict[str, bool]) -> None:
    reason = request_data.reason or ""
    for call in pending_calls:
        approval_id = call.id or call.name
        if approval_id not in approvals:
            continue
        await approval_audit_store.record(
            ApprovalAuditRecord.from_tool_call(
                run_id=run_id,
                call=call,
                approved=approvals[approval_id],
                reason=reason,
            )
        )
