from __future__ import annotations

import typer

from agent.governance.approval_grants import APPROVAL_ALLOW_FOR_RUN, APPROVAL_ALLOW_ONCE, APPROVAL_DENY
from agent.schema import RuntimeEvent


async def print_streaming_turn(session, user_message: str, run_id: str | None = None) -> None:
    state = {"wrote_text": False, "streamed_text": False, "printed_assistant": False}
    status = "finished"
    pending: list[RuntimeEvent] = []
    seen_events: list[RuntimeEvent] = []
    try:
        async for event in session.stream(user_message, run_id=run_id):
            seen_events.append(event)
            status = str(event.payload.get("status") or status) if event.type == "done" else status
            if event.type == "tool_approval_required":
                pending.append(event)
            print_runtime_event(event, state)
        offset = len(seen_events)
        while run_id and status == "awaiting_approval":
            if not pending:
                typer.echo("error: approval required but no pending tool call was returned")
                return
            approvals, approval_scopes = prompt_approvals(pending)
            result = await session.resume(run_id, approvals=approvals, approval_scopes=approval_scopes)
            new_events = _new_events(result.events, offset)
            pending = []
            status = result.status
            for event in new_events:
                if event.type == "tool_approval_required":
                    pending.append(event)
                print_runtime_event(event, state)
            offset = len(result.events)
    except Exception as exc:  # noqa: BLE001 - terminal chat should keep running after one bad turn.
        if state["wrote_text"]:
            typer.echo()
        typer.echo("error: %s" % exc)


def print_runtime_event(event: RuntimeEvent, state: dict) -> None:
    if event.type == "text_delta":
        if not state["wrote_text"]:
            typer.echo("assistant> ", nl=False)
            state["wrote_text"] = True
        state["streamed_text"] = True
        typer.echo(event.payload.get("delta", ""), nl=False)
        return
    if state["wrote_text"]:
        typer.echo()
        state["wrote_text"] = False
    if event.type == "model_message" and event.payload.get("content"):
        typer.echo("assistant> %s" % event.payload["content"])
        state["printed_assistant"] = True
    elif event.type == "tool_start":
        typer.echo("tool> %s" % event.name)
    elif event.type == "tool_result":
        typer.echo("tool result> %s: %s" % (event.name, event.payload.get("content", "")))
    elif event.type == "tool_approval_required":
        call = event.payload.get("tool_call") or {}
        impact = event.payload.get("impact") or {}
        typer.echo("approval> %s risk=%s" % (call.get("name") or event.name, impact.get("risk", "unknown")))
        typer.echo("args> %s" % _compact(call.get("arguments") or {}))
    elif event.type == "tool_approval_decision":
        typer.echo("approval result> %s %s" % (event.name, event.payload.get("scope", "")))
    elif event.type == "error":
        typer.echo("error> %s" % event.payload.get("message", "runtime error"))
    elif (
        event.type == "done"
        and event.payload.get("status") != "awaiting_approval"
        and event.payload.get("content")
        and not state.get("streamed_text")
        and not state.get("printed_assistant")
    ):
        typer.echo("assistant> %s" % event.payload["content"])


def prompt_approvals(events: list[RuntimeEvent]) -> tuple[dict[str, bool], dict[str, str]]:
    approvals: dict[str, bool] = {}
    scopes: dict[str, str] = {}
    for event in events:
        approval_id = str(event.payload.get("approval_id") or event.name)
        call = event.payload.get("tool_call") or {}
        tool_name = call.get("name") or event.name
        choice = typer.prompt(
            "approve %s? [y=yes, r=run, n=no]" % tool_name,
            default="y",
            prompt_suffix=" ",
        ).strip().lower()
        if choice in {"r", "run", "always"}:
            approvals[approval_id] = True
            scopes[approval_id] = APPROVAL_ALLOW_FOR_RUN
        elif choice in {"n", "no", "deny", "d"}:
            approvals[approval_id] = False
            scopes[approval_id] = APPROVAL_DENY
        else:
            approvals[approval_id] = True
            scopes[approval_id] = APPROVAL_ALLOW_ONCE
    return approvals, scopes


def _new_events(events: list[RuntimeEvent], offset: int) -> list[RuntimeEvent]:
    if len(events) < offset:
        return list(events)
    new_events = list(events)[offset:]
    return new_events or list(events)


def _compact(value) -> str:
    text = str(value)
    return text if len(text) <= 220 else text[:217] + "..."
