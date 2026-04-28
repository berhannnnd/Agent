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
from agent.governance.audit import ApprovalAuditRecord
from agent.governance.approval_grants import (
    APPROVAL_ALLOW_FOR_RUN,
    approval_grant_key,
    approval_is_allowed,
    normalize_approval_decision,
)
from agent.config import AgentConfigError
from agent.schema import RuntimeEvent
from agent.tasks import TaskRunner, TaskStatus, TaskStepStatus
from gateway.api.agent.schemas import AgentChatRequest, AgentTaskCreateRequest, RunApprovalRequest
from gateway.core.config import settings
from gateway.services import create_gateway_persistence
from gateway.sessions import (
    GatewayRunService,
    create_trace_recorder,
    run_created_event,
)
from gateway.shared.server.common import resp

router = APIRouter(prefix="/agent")

# 全局并发限制：同时处理的 agent 请求数
_agent_semaphore = asyncio.Semaphore(settings.agent.MAX_CONCURRENT_REQUESTS)
persistence = create_gateway_persistence(settings)
trace_store = persistence.traces
run_service = GatewayRunService(
    persistence.runs,
    trace_recorder=create_trace_recorder(settings, trace_store),
    sandbox_store=persistence.sandboxes,
)
checkpoint_store = persistence.checkpoints
approval_audit_store = persistence.approval_audit


async def create_agent_session(**kwargs):
    return await _create_agent_session_async(
        settings,
        checkpoint_store=checkpoint_store,
        memory_store=persistence.memories,
        sandbox_store=persistence.sandboxes,
        **kwargs,
    )


class _TaskSessionFactory:
    async def create(self, task):
        return await create_agent_session(spec=task.to_agent_spec(), task_id=task.task_id)


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


@router.get("/runs/{run_id}/trace")
async def get_run_trace(run_id: str):
    record = await run_service.store.load_run(run_id)
    if record is None:
        return resp.fail(resp.Resp(code="404", detail="run not found: %s" % run_id, http_status=404))
    spans = await trace_store.list_for_run(run_id)
    approvals = await approval_audit_store.list_for_run(run_id)
    sandbox_leases = await persistence.sandboxes.list_leases_for_run(run_id)
    sandbox_events = await persistence.sandboxes.list_events_for_run(run_id)
    sandbox_snapshots = await persistence.sandboxes.list_workspace_snapshots_for_run(run_id)
    return resp.ok(
        response=resp.Resp(
            data={
                "run_id": run_id,
                "spans": [span.to_dict() for span in spans],
                "approvals": [approval.to_dict() for approval in approvals],
                "sandbox_leases": [lease.to_dict() for lease in sandbox_leases],
                "sandbox_artifacts": _sandbox_artifacts(sandbox_leases),
                "sandbox_events": [event.to_dict() for event in sandbox_events],
                "sandbox_snapshots": [snapshot.to_dict() for snapshot in sandbox_snapshots],
            }
        )
    )


@router.post("/tasks")
async def create_task(request_data: AgentTaskCreateRequest):
    spec = request_data.to_agent_spec()
    task = await persistence.tasks.create_task(
        spec,
        title=request_data.title or _default_task_title(request_data.message),
        input=request_data.message,
        metadata=request_data.metadata,
    )
    return resp.ok(response=resp.Resp(data=task.to_dict()))


@router.get("/tasks")
async def list_tasks(tenant_id: str = "", user_id: str = "", agent_id: str = ""):
    tasks = await persistence.tasks.list_tasks(tenant_id, user_id=user_id, agent_id=agent_id)
    return resp.ok(response=resp.Resp(data={"tasks": [task.to_dict() for task in tasks]}))


@router.get("/tasks/{task_id}")
async def get_task(task_id: str):
    task = await persistence.tasks.load_task(task_id)
    if task is None:
        return resp.fail(resp.Resp(code="404", detail="task not found: %s" % task_id, http_status=404))
    steps = await persistence.tasks.list_steps(task_id)
    return resp.ok(
        response=resp.Resp(
            data={
                "task": task.to_dict(),
                "steps": [step.to_dict() for step in steps],
            }
        )
    )


@router.post("/tasks/{task_id}/run")
async def run_task(task_id: str):
    async with _agent_semaphore:
        task = await persistence.tasks.load_task(task_id)
        if task is None:
            return resp.fail(resp.Resp(code="404", detail="task not found: %s" % task_id, http_status=404))
        try:
            result = await TaskRunner(persistence.tasks, run_service, _TaskSessionFactory()).run_task(task_id)
        except AgentConfigError as exc:
            return resp.fail(resp.Resp(code="400", detail={"task_id": task_id, "message": str(exc)}, http_status=400))
        except Exception as exc:  # noqa: BLE001 - task API must report persisted runner failures.
            return resp.fail(resp.Resp(code="500", detail={"task_id": task_id, "message": str(exc)}, http_status=500))
        return resp.ok(
            response=resp.Resp(
                data={
                    "task": result.task.to_dict(),
                    "step": result.step.to_dict(),
                    "run": (await run_service.store.load_run(result.run.run_id) or result.run).to_dict(),
                    "result": {
                        "status": result.result.status,
                        "content": result.result.content,
                        "events": [event.to_dict() for event in result.result.events],
                    },
                }
            )
        )


@router.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    task = await persistence.tasks.load_task(task_id)
    if task is None:
        return resp.fail(resp.Resp(code="404", detail="task not found: %s" % task_id, http_status=404))
    canceled = await TaskRunner(persistence.tasks, run_service, _TaskSessionFactory()).cancel_task(task_id)
    return resp.ok(response=resp.Resp(data=canceled.to_dict()))


@router.post("/runs/{run_id}/approval")
async def approve_run_tools(run_id: str, request_data: RunApprovalRequest):
    async with _agent_semaphore:
        record = await run_service.store.load_run(run_id)
        if record is None:
            return resp.fail(resp.Resp(code="404", detail="run not found: %s" % run_id, http_status=404))
        checkpoint = await checkpoint_store.load(run_id)
        if checkpoint is None or not checkpoint.pending_tool_calls:
            return resp.fail(resp.Resp(code="409", detail="run is not waiting for tool approval", http_status=409))

        try:
            approval_scopes = _approval_decision_map(request_data, checkpoint.pending_tool_calls)
            approvals = _approval_map(approval_scopes)
            approval_grants = _approval_grants(checkpoint.pending_tool_calls, approvals, approval_scopes)
        except ValueError as exc:
            return resp.fail(resp.Resp(code="400", detail=str(exc), http_status=400))
        try:
            await _record_approval_audit(run_id, request_data, checkpoint.pending_tool_calls, approvals, approval_scopes)
            await run_service.mark_running(run_id)
            session = await create_agent_session(spec=record.to_agent_spec())
            step = await persistence.tasks.load_step_for_run(run_id)
            result = await session.resume(
                run_id,
                approvals=approvals,
                approval_scopes=approval_scopes,
                approval_grants=approval_grants,
                task_id=step.task_id if step else None,
            )
            new_events = _new_runtime_events(record.events, result.events)
            await run_service.record_events(run_id, new_events)
            await _complete_or_pause(run_id, result.status, new_events)
            await _sync_task_for_run(run_id, result.status, result.content, new_events)
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


def _default_task_title(message: str) -> str:
    text = " ".join(str(message or "").split())
    return text[:80] or "Untitled task"


def _sandbox_artifacts(leases) -> dict:
    root = "artifacts"
    for lease in leases:
        root = lease.metadata.get("artifacts_root") or root
        break
    return {
        "root": root,
        "downloads": "%s/downloads" % root,
        "screenshots": "%s/screenshots" % root,
        "logs": "%s/logs" % root,
        "snapshots": "%s/snapshots" % root,
    }


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


async def _sync_task_for_run(run_id: str, status: str, content: str, events) -> None:
    step = await persistence.tasks.load_step_for_run(run_id)
    if step is None:
        return
    if status == "awaiting_approval" or any(event.type == "tool_approval_required" for event in events):
        await persistence.tasks.update_step_status(step.step_id, TaskStepStatus.AWAITING_APPROVAL)
        await persistence.tasks.set_task_status(step.task_id, TaskStatus.AWAITING_APPROVAL)
        return
    error = _result_error(events)
    if error or status not in {"finished", ""}:
        await persistence.tasks.update_step_status(step.step_id, TaskStepStatus.FAILED, error=error or content)
        await persistence.tasks.set_task_status(step.task_id, TaskStatus.ERROR)
        return
    await persistence.tasks.update_step_status(step.step_id, TaskStepStatus.SUCCEEDED, output=content)
    await persistence.tasks.set_task_status(step.task_id, TaskStatus.FINISHED)


async def _fail_run(run_id: str, kind: str, message: str) -> None:
    await run_service.record_event(run_id, RuntimeEvent(type="error", name=kind, payload={"message": message}))
    await run_service.finish(run_id, message)


def _approval_decision_map(request_data: RunApprovalRequest, pending_calls) -> dict[str, str]:
    if request_data.decisions:
        return {str(key): normalize_approval_decision(value) for key, value in request_data.decisions.items()}
    if request_data.approvals:
        return {str(key): normalize_approval_decision(value) for key, value in request_data.approvals.items()}
    pending_ids = [call.id or call.name for call in pending_calls]
    selected = request_data.tool_call_ids or pending_ids
    decision = normalize_approval_decision(request_data.decision, request_data.approved)
    return {str(item): decision for item in selected}


def _approval_map(decisions: dict[str, str]) -> dict[str, bool]:
    return {approval_id: approval_is_allowed(decision) for approval_id, decision in decisions.items()}


def _approval_grants(pending_calls, approvals: dict[str, bool], decisions: dict[str, str]) -> dict[str, bool]:
    grants: dict[str, bool] = {}
    for call in pending_calls:
        approval_id = call.id or call.name
        if approvals.get(approval_id) and decisions.get(approval_id) == APPROVAL_ALLOW_FOR_RUN:
            grants[approval_grant_key(call)] = True
    return grants


def _new_runtime_events(record_events, result_events) -> list[RuntimeEvent]:
    recorded_runtime_events = [event for event in record_events if event.type != "run_created"]
    return list(result_events)[len(recorded_runtime_events):]


async def _record_approval_audit(
    run_id: str,
    request_data: RunApprovalRequest,
    pending_calls,
    approvals: dict[str, bool],
    decisions: dict[str, str],
) -> None:
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
                decision=decisions.get(approval_id, ""),
                reason=reason,
            )
        )
