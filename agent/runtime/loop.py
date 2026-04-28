from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterable, List, Mapping, Optional

from agent.hooks import AgentHooks
from agent.models.errors import ModelClientError
from agent.runtime.checkpoints import CheckpointStore, NullCheckpointStore, RuntimeCheckpoint
from agent.runtime.config import RuntimeConfig
from agent.runtime.errors import AgentRuntimeError
from agent.runtime.events import (
    error_event,
    model_message_event,
    tool_approval_decision_event,
    tool_approval_id,
    tool_approval_required_event,
    tool_start_event,
)
from agent.governance.permissions import ToolPermissionDecision, ToolPermissionPolicy
from agent.context.compiler import ModelRequestCompiler
from agent.runtime.state import RuntimeState
from agent.runtime.turns import ModelTurnRunner, ToolOrchestrator
from agent.runtime.types import AgentResult, ModelClientProtocol
from agent.schema import Message, ModelResponse, RuntimeEvent, ToolCall
from agent.capabilities.tools.registry import ToolRegistry


@dataclass(frozen=True)
class ToolExecutionOutcome:
    events: List[RuntimeEvent]
    approval_required: bool = False


class AgentRuntime:
    def __init__(
        self,
        model_client: ModelClientProtocol,
        tools: ToolRegistry,
        provider: str,
        model: str,
        enabled_tools: List[str] = None,
        max_tool_iterations: int = 8,
        hooks: Optional[AgentHooks] = None,
        permission_policy: Optional[ToolPermissionPolicy] = None,
        checkpoint_store: Optional[CheckpointStore] = None,
    ):
        self.model_client = model_client
        self.tools = tools
        self.config = RuntimeConfig(
            provider=provider,
            model=model,
            enabled_tools=list(enabled_tools or []),
            max_tool_iterations=max_tool_iterations,
        )
        self.hooks = hooks or AgentHooks()
        self.model_request_compiler = ModelRequestCompiler(tools)
        self.model_turn_runner = ModelTurnRunner(self.model_client, self.model_request_compiler, self.hooks)
        self.tool_orchestrator = ToolOrchestrator(tools, self.hooks, permission_policy=permission_policy)
        self.checkpoints = checkpoint_store or NullCheckpointStore()

    @property
    def provider(self) -> str:
        return self.config.provider

    @property
    def model(self) -> str:
        return self.config.model

    @property
    def enabled_tools(self) -> List[str]:
        return list(self.config.enabled_tools)

    @property
    def max_tool_iterations(self) -> int:
        return self.config.max_tool_iterations

    async def run(self, messages: List[Message], run_id: str | None = None, task_id: str | None = None) -> AgentResult:
        return await self._run_state(RuntimeState.from_messages(messages), run_id=run_id, task_id=task_id)

    async def resume(
        self,
        run_id: str,
        approvals: Mapping[str, bool] | None = None,
        task_id: str | None = None,
    ) -> AgentResult:
        checkpoint = await self.checkpoints.load(run_id)
        if checkpoint is None:
            raise AgentRuntimeError("checkpoint not found: %s" % run_id)
        state = checkpoint.to_state()
        if approvals:
            state.tool_approvals.update({str(key): bool(value) for key, value in approvals.items()})
        return await self._run_state(state, run_id=run_id, task_id=task_id)

    async def _run_state(
        self,
        state: RuntimeState,
        run_id: str | None = None,
        task_id: str | None = None,
    ) -> AgentResult:
        try:
            if state.pending_tool_calls:
                outcome = await self._execute_pending_tools(state, run_id, task_id)
                if outcome.approval_required:
                    return self._approval_result(state)
                state.iteration += 1

            while state.iteration < self.config.max_tool_iterations:
                response = await self._complete_once(state.messages)
                calls = await self._apply_model_response(state, response, run_id)
                if not calls:
                    return AgentResult(response.content_text(), state.messages, state.tool_results, state.events)
                outcome = await self._execute_pending_tools(state, run_id, task_id)
                if outcome.approval_required:
                    return self._approval_result(state)
                state.iteration += 1
        except ModelClientError as exc:
            recovery = await self.hooks.on_error(exc, state.messages)
            if recovery is not None:
                return recovery
            error_msg = "model error: %s" % exc
            await self._record_error(state, run_id, "model", error_msg)
            return AgentResult(error_msg, state.messages, state.tool_results, state.events)
        except AgentRuntimeError as exc:
            recovery = await self.hooks.on_error(exc, state.messages)
            if recovery is not None:
                return recovery
            error_msg = str(exc)
            await self._record_error(state, run_id, "runtime", error_msg)
            return AgentResult(error_msg, state.messages, state.tool_results, state.events)
        except Exception as exc:
            recovery = await self.hooks.on_error(exc, state.messages)
            if recovery is not None:
                return recovery
            error_msg = "unexpected error: %s" % exc
            await self._record_error(state, run_id, "runtime", error_msg)
            return AgentResult(error_msg, state.messages, state.tool_results, state.events)
        error_msg = "tool-call loop exceeded max iterations"
        await self._record_error(state, run_id, "runtime", error_msg)
        return AgentResult(error_msg, state.messages, state.tool_results, state.events)

    async def stream(
        self,
        messages: List[Message],
        run_id: str | None = None,
        task_id: str | None = None,
    ) -> AsyncIterable[RuntimeEvent]:
        state = RuntimeState.from_messages(messages)
        error_msg = None
        terminal_status = "finished"
        terminal_content = ""
        try:
            while state.iteration < self.config.max_tool_iterations:
                final_response = None
                async for update in self.model_turn_runner.stream(state.messages, self.config):
                    if update.event is not None:
                        yield update.event
                    if update.response is not None:
                        final_response = update.response
                if final_response is None:
                    raise AgentRuntimeError("model stream did not include final message")

                calls = await self._apply_model_response(state, final_response, run_id)
                if not calls:
                    terminal_content = final_response.content_text()
                    return
                outcome = await self._execute_pending_tools(state, run_id, task_id)
                for event in outcome.events:
                    yield event
                if outcome.approval_required:
                    terminal_status = "awaiting_approval"
                    terminal_content = "tool approval required"
                    return
                state.iteration += 1
            error_msg = "tool-call loop exceeded max iterations"
            yield await self._record_error(state, run_id, "runtime", error_msg)
        except ModelClientError as exc:
            error_msg = "model error: %s" % exc
            yield await self._record_error(state, run_id, "model", error_msg)
        except AgentRuntimeError as exc:
            error_msg = str(exc)
            yield await self._record_error(state, run_id, "runtime", error_msg)
        except Exception as exc:
            error_msg = "unexpected error: %s" % exc
            yield await self._record_error(state, run_id, "runtime", error_msg)
        finally:
            yield RuntimeEvent(
                type="done",
                name="assistant",
                payload={
                    "content": error_msg or terminal_content or (state.messages[-1].content_text() if state.messages else ""),
                    "messages": [message.to_dict() for message in state.messages],
                    "error": error_msg,
                    "status": "error" if error_msg else terminal_status,
                },
            )

    async def _complete_once(self, messages: List[Message]) -> ModelResponse:
        return await self.model_turn_runner.complete(messages, self.config)

    async def _apply_model_response(
        self,
        state: RuntimeState,
        response: ModelResponse,
        run_id: str | None,
    ) -> List[ToolCall]:
        state.messages.append(response.message)
        state.events.append(model_message_event(response))
        calls = response.tool_calls
        if not calls:
            await self._save_checkpoint(run_id, "finished", state)
            return []
        state.pending_tool_calls = list(calls)
        await self._save_checkpoint(run_id, "model_response", state)
        return calls

    async def _execute_pending_tools(
        self,
        state: RuntimeState,
        run_id: str | None,
        task_id: str | None = None,
    ) -> ToolExecutionOutcome:
        if not state.pending_tool_calls:
            return ToolExecutionOutcome([])
        emitted: List[RuntimeEvent] = []
        authorizations = await self.tool_orchestrator.authorize(state.pending_tool_calls)
        approval_events = []
        for item in authorizations:
            approval_id = tool_approval_id(item.call)
            if approval_id in state.tool_approvals:
                continue
            if item.decision.requires_approval:
                approval_events.append(tool_approval_required_event(item.call, item.decision))
        if approval_events:
            state.events.extend(approval_events)
            await self._save_checkpoint(run_id, "approval_required", state)
            return ToolExecutionOutcome(approval_events, approval_required=True)

        decisions: List[ToolPermissionDecision] = []
        approved_call_ids: set[str] = set()
        for item in authorizations:
            approval_id = tool_approval_id(item.call)
            if approval_id in state.tool_approvals:
                approved = state.tool_approvals[approval_id]
                approved_call_ids.add(approval_id)
                event = tool_approval_decision_event(item.call, approved)
                state.events.append(event)
                emitted.append(event)
                decisions.append(
                    ToolPermissionDecision(
                        allowed=approved,
                        reason="" if approved else "tool denied by user approval",
                        metadata={"source": "user_approval"},
                    )
                )
                continue
            decisions.append(item.decision)

        for call, decision in zip(state.pending_tool_calls, decisions):
            if not decision.allowed:
                continue
            event = tool_start_event(call.name, call.to_dict())
            state.events.append(event)
            emitted.append(event)
        batch = await self.tool_orchestrator.execute_with_decisions(
            state.pending_tool_calls,
            decisions,
            run_id=run_id or "",
            task_id=task_id or "",
        )
        state.tool_results.extend(batch.results)
        state.events.extend(batch.events)
        emitted.extend(batch.events)
        state.messages.extend(batch.messages)
        for approval_id in approved_call_ids:
            state.tool_approvals.pop(approval_id, None)
        state.pending_tool_calls = []
        await self._save_checkpoint(run_id, "tool_results", state)
        return ToolExecutionOutcome(emitted)

    async def _record_error(
        self,
        state: RuntimeState,
        run_id: str | None,
        kind: str,
        message: str,
    ) -> RuntimeEvent:
        event = error_event(kind, message)
        state.events.append(event)
        await self._save_checkpoint(run_id, "error", state)
        return event

    async def _save_checkpoint(self, run_id: str | None, step: str, state: RuntimeState) -> None:
        if run_id is None:
            return
        await self.checkpoints.save(RuntimeCheckpoint.from_state(run_id, step, state))

    def _approval_result(self, state: RuntimeState) -> AgentResult:
        return AgentResult(
            "tool approval required",
            state.messages,
            state.tool_results,
            state.events,
            status="awaiting_approval",
        )
