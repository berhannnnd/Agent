from __future__ import annotations

from typing import AsyncIterable, List, Optional

from agent.hooks import AgentHooks
from agent.models.errors import ModelClientError
from agent.runtime.checkpoints import CheckpointStore, NullCheckpointStore, RuntimeCheckpoint
from agent.runtime.config import RuntimeConfig
from agent.runtime.errors import AgentRuntimeError
from agent.runtime.events import error_event, model_message_event, tool_start_event
from agent.security.permissions import ToolPermissionPolicy
from agent.context.compiler import ModelRequestCompiler
from agent.runtime.state import RuntimeState
from agent.runtime.turns import ModelTurnRunner, ToolOrchestrator
from agent.runtime.types import AgentResult, ModelClientProtocol
from agent.schema import Message, ModelResponse, RuntimeEvent, ToolCall
from agent.tools.registry import ToolRegistry


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

    async def run(self, messages: List[Message], run_id: str | None = None) -> AgentResult:
        return await self._run_state(RuntimeState.from_messages(messages), run_id=run_id)

    async def resume(self, run_id: str) -> AgentResult:
        checkpoint = await self.checkpoints.load(run_id)
        if checkpoint is None:
            raise AgentRuntimeError("checkpoint not found: %s" % run_id)
        return await self._run_state(checkpoint.to_state(), run_id=run_id)

    async def _run_state(self, state: RuntimeState, run_id: str | None = None) -> AgentResult:
        try:
            if state.pending_tool_calls:
                await self._execute_pending_tools(state, run_id)
                state.iteration += 1

            while state.iteration < self.config.max_tool_iterations:
                response = await self._complete_once(state.messages)
                calls = await self._apply_model_response(state, response, run_id)
                if not calls:
                    return AgentResult(response.content_text(), state.messages, state.tool_results, state.events)
                await self._execute_pending_tools(state, run_id)
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

    async def stream(self, messages: List[Message], run_id: str | None = None) -> AsyncIterable[RuntimeEvent]:
        state = RuntimeState.from_messages(messages)
        error_msg = None
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
                    return
                for event in await self._execute_pending_tools(state, run_id):
                    yield event
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
                    "content": error_msg or (state.messages[-1].content_text() if state.messages else ""),
                    "messages": [message.to_dict() for message in state.messages],
                    "error": error_msg,
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

    async def _execute_pending_tools(self, state: RuntimeState, run_id: str | None) -> List[RuntimeEvent]:
        if not state.pending_tool_calls:
            return []
        emitted: List[RuntimeEvent] = []
        for call in state.pending_tool_calls:
            event = tool_start_event(call.name, call.to_dict())
            state.events.append(event)
            emitted.append(event)
        batch = await self.tool_orchestrator.execute(state.pending_tool_calls)
        state.tool_results.extend(batch.results)
        state.events.extend(batch.events)
        emitted.extend(batch.events)
        state.messages.extend(batch.messages)
        state.pending_tool_calls = []
        await self._save_checkpoint(run_id, "tool_results", state)
        return emitted

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
