from __future__ import annotations

import typer

from agent.governance.approval_grants import APPROVAL_ALLOW_FOR_RUN, APPROVAL_ALLOW_ONCE, APPROVAL_DENY
from agent.schema import RuntimeEvent
from cli.ui.activity import TurnActivity
from cli.ui import TerminalUI


async def print_streaming_turn(session, user_message: str, run_id: str | None = None, ui: TerminalUI | None = None) -> None:
    ui = ui or TerminalUI()
    state = TurnActivity()
    status = "finished"
    pending: list[RuntimeEvent] = []
    seen_events: list[RuntimeEvent] = []
    try:
        state = ui.turn_started(session, state)
        async for event in session.stream(user_message, run_id=run_id):
            seen_events.append(event)
            status = str(event.payload.get("status") or status) if event.type == "done" else status
            if event.type == "tool_approval_required":
                pending.append(event)
            print_runtime_event(event, state, ui)
        ui.turn_finished(status=status, state=state)
        offset = len(seen_events)
        while run_id and status == "awaiting_approval":
            if not pending:
                ui.error("approval required but no pending tool call was returned")
                return
            approvals, approval_scopes = prompt_approvals(pending)
            result = await session.resume(run_id, approvals=approvals, approval_scopes=approval_scopes)
            new_events = _new_events(result.events, offset)
            pending = []
            status = result.status
            for event in new_events:
                if event.type == "tool_approval_required":
                    pending.append(event)
                print_runtime_event(event, state, ui)
            ui.turn_finished(status=status, state=state)
            offset = len(result.events)
    except Exception as exc:  # noqa: BLE001 - terminal chat should keep running after one bad turn.
        ui.finish_assistant_stream(state)
        ui.flush_tool_summary(state)
        ui.error(str(exc))
        ui.turn_finished(status="error", state=state)


def print_runtime_event(event: RuntimeEvent, state: TurnActivity, ui: TerminalUI | None = None) -> None:
    (ui or TerminalUI()).runtime_event(event, state)


def prompt_approvals(events: list[RuntimeEvent]) -> tuple[dict[str, bool], dict[str, str]]:
    approvals: dict[str, bool] = {}
    scopes: dict[str, str] = {}
    for event in events:
        approval_id = str(event.payload.get("approval_id") or event.name)
        call = event.payload.get("tool_call") or {}
        tool_name = call.get("name") or event.name
        choice = typer.prompt(
            "Approve %s? [y=yes, r=this run, n=no]" % tool_name,
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
