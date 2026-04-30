from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from agent.assembly import create_agent_session_async
from agent.config import (
    AgentConfigError,
    ModelProfile,
    active_profile_name,
    build_model_profiles,
    resolve_model_profile,
    runtime_settings,
)
from agent.config.paths import ENV_FILE
from agent.governance.approval_grants import (
    APPROVAL_ALLOW_ONCE,
    APPROVAL_DENY,
    normalize_approval_decision,
)
from agent.runtime import InMemoryCheckpointStore
from agent.schema import RuntimeEvent
from agent.specs import AgentSpec
from cli.commands import COMMANDS
from cli.profiles import (
    enabled_tools,
    local_user_id,
    normalize_profile,
    permission_settings,
    settings_for_cli,
    system_prompt as cli_system_prompt,
    workspace_path as resolve_cli_workspace_path,
)


@dataclass
class BridgeState:
    args: argparse.Namespace
    profile: str
    permission: str
    active_workspace: Path | None
    active_tools: list[str]
    permission_mode: str
    approval_tools: list[str]
    settings: Any
    checkpoint_store: InMemoryCheckpointStore
    model_profiles: list[ModelProfile]
    session: Any
    event_offsets: dict[str, int]


async def main_async(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        state = await _create_state(args)
    except AgentConfigError as exc:
        _write({"type": "error", "message": str(exc)})
        return 2
    _write_ready(state)

    while True:
        line = await asyncio.to_thread(sys.stdin.readline)
        if not line:
            break
        try:
            command = json.loads(line)
        except json.JSONDecodeError as exc:
            _write({"type": "error", "message": "invalid json: %s" % exc})
            continue
        should_continue = await _handle_command(state, command)
        if not should_continue:
            break
    await _close_session_model_client(state.session)
    return 0


def main(argv: list[str] | None = None) -> None:
    raise SystemExit(asyncio.run(main_async(argv)))


async def _create_state(args: argparse.Namespace) -> BridgeState:
    profile = normalize_profile(args.profile)
    active_workspace = resolve_cli_workspace_path(profile, Path(args.workspace_path) if args.workspace_path else None)
    active_tools = enabled_tools(profile, args.tools)
    permission_mode, approval_tools = permission_settings(args.permission, profile)
    settings = settings_for_cli(profile, args.sandbox_provider)
    model_profiles = build_model_profiles(settings)
    checkpoint_store = InMemoryCheckpointStore()
    selected = resolve_model_profile(model_profiles, args.model_profile) if args.model_profile else None
    if args.model_profile and selected is None:
        raise AgentConfigError("unknown model profile: %s" % args.model_profile)
    session = await _make_session(
        args,
        settings=settings,
        checkpoint_store=checkpoint_store,
        profile=profile,
        active_workspace=active_workspace,
        active_tools=active_tools,
        permission_mode=permission_mode,
        approval_tools=approval_tools,
        model_profile=selected,
    )
    return BridgeState(
        args=args,
        profile=profile,
        permission=args.permission,
        active_workspace=active_workspace,
        active_tools=active_tools,
        permission_mode=permission_mode,
        approval_tools=approval_tools,
        settings=settings,
        checkpoint_store=checkpoint_store,
        model_profiles=model_profiles,
        session=session,
        event_offsets={},
    )


async def _make_session(
    args: argparse.Namespace,
    *,
    settings: Any,
    checkpoint_store: InMemoryCheckpointStore,
    profile: str,
    active_workspace: Path | None,
    active_tools: list[str],
    permission_mode: str,
    approval_tools: list[str],
    model_profile: ModelProfile | None,
):
    user_id = args.user_id or local_user_id()
    agent_id = args.agent_id or "cli"
    workspace_id = args.workspace_id or (active_workspace.name if active_workspace else "")
    system_prompt = cli_system_prompt(args.system, profile, active_workspace)
    return await create_agent_session_async(
        settings,
        checkpoint_store=checkpoint_store,
        spec=AgentSpec.from_overrides(
            protocol=model_profile.protocol if model_profile else None,
            model=model_profile.model if model_profile else None,
            base_url=model_profile.base_url if model_profile else None,
            api_key=model_profile.api_key if model_profile else None,
            system_prompt=system_prompt,
            enabled_tools=active_tools,
            tenant_id=args.tenant_id or "",
            user_id=user_id,
            agent_id=agent_id,
            workspace_id=workspace_id,
            workspace_path=str(active_workspace) if active_workspace else "",
            permission_profile=permission_mode,
            approval_required_tools=approval_tools,
        ),
    )


async def _handle_command(state: BridgeState, command: dict[str, Any]) -> bool:
    command_type = str(command.get("type") or "")
    if command_type == "exit":
        return False
    if command_type == "user_message":
        await _run_turn(state, str(command.get("text") or ""), str(command.get("run_id") or _run_id()))
        return True
    if command_type == "approval":
        await _run_approval(state, command)
        return True
    if command_type == "slash":
        await _run_slash(state, str(command.get("text") or ""))
        return True
    _write({"type": "error", "message": "unknown bridge command: %s" % command_type})
    return True


async def _run_turn(state: BridgeState, text: str, run_id: str) -> None:
    if not text.strip():
        return
    _write({"type": "turn_started", "run_id": run_id})
    status = "finished"
    persisted_events = 0
    try:
        async for event in state.session.stream(text, run_id=run_id):
            if event.type == "done":
                status = str(event.payload.get("status") or status)
            elif _is_persisted_runtime_event(event):
                persisted_events += 1
            _write({"type": "runtime_event", "event": event.to_dict()})
    except Exception as exc:  # noqa: BLE001 - bridge must keep the client alive after one bad turn.
        status = "error"
        _write({"type": "runtime_event", "event": {"type": "error", "name": "bridge", "payload": {"message": str(exc)}}})
    state.event_offsets[run_id] = persisted_events
    _write({"type": "turn_finished", "status": status, "run_id": run_id})


async def _run_approval(state: BridgeState, command: dict[str, Any]) -> None:
    run_id = str(command.get("run_id") or "")
    if not run_id:
        _write({"type": "error", "message": "approval command requires run_id"})
        return
    approvals_payload = command.get("approvals") if isinstance(command.get("approvals"), dict) else {}
    scopes_payload = command.get("approval_scopes") if isinstance(command.get("approval_scopes"), dict) else {}
    approvals: dict[str, bool] = {}
    approval_scopes: dict[str, str] = {}
    for approval_id, raw_approved in approvals_payload.items():
        approval_key = str(approval_id)
        approved = bool(raw_approved)
        raw_scope = scopes_payload.get(approval_key, APPROVAL_ALLOW_ONCE if approved else APPROVAL_DENY)
        try:
            scope = normalize_approval_decision(raw_scope, approved=approved)
        except ValueError as exc:
            _write({"type": "error", "message": str(exc)})
            return
        approvals[approval_key] = scope != APPROVAL_DENY
        approval_scopes[approval_key] = scope if approvals[approval_key] else APPROVAL_DENY
    status = "finished"
    try:
        result = await state.session.resume(run_id, approvals=approvals, approval_scopes=approval_scopes)
        for event in _new_events(result.events, state.event_offsets.get(run_id, 0)):
            _write({"type": "runtime_event", "event": event.to_dict()})
        state.event_offsets[run_id] = len(result.events)
        status = result.status
    except Exception as exc:  # noqa: BLE001 - keep the bridge process alive after a failed resume.
        status = "error"
        _write({"type": "runtime_event", "event": {"type": "error", "name": "bridge", "payload": {"message": str(exc)}}})
    _write({"type": "turn_finished", "status": status, "run_id": run_id})


async def _run_slash(state: BridgeState, value: str) -> None:
    parts = value.strip().split(maxsplit=1)
    command = parts[0] if parts else ""
    argument = parts[1] if len(parts) > 1 else ""
    if command in {"/quit", "/exit"}:
        _write({"type": "exit"})
        return
    if command == "/clear":
        state.session.clear()
        _write({"type": "notice", "message": "cleared"})
        return
    if command in {"/help", "?"}:
        _write({"type": "commands", "commands": [{"name": item.name, "action": item.action, "aliases": list(item.aliases)} for item in COMMANDS]})
        return
    if command in {"/model", "/models"}:
        if argument:
            profile = resolve_model_profile(state.model_profiles, argument)
            if profile is None:
                _write({"type": "error", "message": "unknown model profile: %s" % argument})
                return
            previous_messages = list(getattr(state.session, "messages", []))
            await _close_session_model_client(state.session)
            state.session = await _make_session(
                state.args,
                settings=state.settings,
                checkpoint_store=state.checkpoint_store,
                profile=state.profile,
                active_workspace=state.active_workspace,
                active_tools=state.active_tools,
                permission_mode=state.permission_mode,
                approval_tools=state.approval_tools,
                model_profile=profile,
            )
            state.session.messages = previous_messages
            _write({"type": "model_switched", "profile": profile.name, "runtime": _runtime_payload(state)})
        _write({"type": "model_profiles", "profiles": _model_profiles_payload(state)})
        return
    if command == "/status":
        _write({"type": "status", "status": _status_payload(state)})
        return
    if command == "/tools":
        _write({"type": "tools", "tools": list(state.active_tools)})
        return
    if command == "/workspace":
        _write({"type": "workspace", "workspace": _workspace_payload(state)})
        return
    if command == "/context":
        _write({"type": "context", "context": _context_payload(state)})
        return
    if command == "/trace":
        _write({"type": "trace", "trace": _trace_payload(state)})
        return
    if command == "/doctor":
        _write({"type": "doctor", "doctor": _doctor_payload(state)})
        return
    _write({"type": "error", "message": "unknown command: %s" % value})


def _write_ready(state: BridgeState) -> None:
    _write(
        {
            "type": "ready",
            "runtime": _runtime_payload(state),
            "workspace": _workspace_payload(state),
            "profile": state.profile,
            "permission": state.permission,
            "sandbox": str(getattr(state.settings.agent, "SANDBOX_PROVIDER", "local")),
            "tools": list(state.active_tools),
            "commands": [item.name for item in COMMANDS[:4]],
        }
    )


def _runtime_payload(state: BridgeState) -> dict[str, Any]:
    return {
        "protocol": str(state.session.runtime.protocol),
        "model": str(state.session.runtime.model),
        "model_profile": active_profile_name(
            state.model_profiles,
            state.session.runtime.protocol,
            state.session.runtime.model,
            _model_base_url(state.session),
        ),
        "endpoint": _model_endpoint(state.session),
    }


def _model_profiles_payload(state: BridgeState) -> list[dict[str, Any]]:
    active_protocol = str(state.session.runtime.protocol)
    active_model = str(state.session.runtime.model)
    active_base_url = _model_base_url(state.session).rstrip("/")
    rows = []
    for profile in state.model_profiles:
        profile_base_url = str(profile.base_url or "").rstrip("/")
        rows.append(
            {
                "name": profile.name,
                "protocol": profile.protocol,
                "model": profile.model,
                "endpoint": profile.endpoint,
                "configured": profile.configured,
                "active": profile.protocol == active_protocol
                and profile.model == active_model
                and (not active_base_url or not profile_base_url or profile_base_url == active_base_url),
            }
        )
    return rows


def _workspace_payload(state: BridgeState) -> dict[str, Any]:
    workspace = getattr(state.session, "workspace", None)
    if workspace is None:
        return {"path": "", "display": "no workspace"}
    return {
        "path": str(workspace.path),
        "display": _short_path(str(workspace.path)),
        "tenant_id": workspace.tenant_id,
        "user_id": workspace.user_id,
        "agent_id": workspace.agent_id,
        "workspace_id": workspace.workspace_id,
    }


def _status_payload(state: BridgeState) -> dict[str, str]:
    payload = {
        "model": "%s · %s" % (state.session.runtime.protocol, state.session.runtime.model),
        "profile": state.profile,
        "permission": state.permission,
        "messages": str(max(0, len(getattr(state.session, "messages", [])) - 1)),
        "tokens": _estimate_session_tokens(state.session),
        "tools": str(len(state.active_tools)),
    }
    endpoint = _model_endpoint(state.session)
    if endpoint:
        payload["endpoint"] = endpoint
    return payload


def _context_payload(state: BridgeState) -> dict[str, str]:
    return {
        "tokens": _estimate_session_tokens(state.session),
        "limit": str(getattr(state.session, "max_context_tokens", "")),
        "messages": str(len(getattr(state.session, "messages", []))),
        "trace_items": str(len(getattr(state.session, "context_trace", []))),
    }


def _doctor_payload(state: BridgeState) -> dict[str, str]:
    return {
        "env_file": ENV_FILE,
        "model": "%s · %s" % (state.session.runtime.protocol, state.session.runtime.model),
        "endpoint": _model_endpoint(state.session) or "not exposed",
        "timeout": str(getattr(state.settings.agent, "TIMEOUT", "")),
        "max_retries": str(getattr(state.settings.agent, "MAX_RETRIES", "")),
        "retry_base_delay": str(getattr(state.settings.agent, "RETRY_BASE_DELAY", "")),
        "configured_profiles": str(len([profile for profile in state.model_profiles if profile.configured])),
        "enabled_tools": str(len(state.active_tools)),
        "workspace": _workspace_payload(state).get("path", "not bound"),
    }


def _trace_payload(state: BridgeState) -> list[list[str]]:
    trace = list(getattr(state.session, "context_trace", []) or [])
    rows: list[list[str]] = []
    for item in trace[:30]:
        layer = getattr(getattr(item, "layer", ""), "value", getattr(item, "layer", ""))
        source = str(getattr(item, "source", ""))
        status = "in" if bool(getattr(item, "included", False)) else "out"
        tokens = str(getattr(item, "tokens", ""))
        reason = str(getattr(item, "reason", ""))
        rows.append([str(layer), "%s · %s tokens · %s%s" % (source, tokens, status, (" · " + reason) if reason else "")])
    if len(trace) > 30:
        rows.append(["...", "%s more" % (len(trace) - 30)])
    if not rows:
        rows.append(["trace", "not available"])
    return rows


def _estimate_session_tokens(session: Any) -> str:
    try:
        return str(session._estimate_tokens(getattr(session, "messages", [])))
    except Exception:
        return "unknown"


async def _close_session_model_client(session: Any) -> None:
    runtime = getattr(session, "runtime", None)
    model_client = getattr(runtime, "model_client", None)
    close = getattr(model_client, "async_close", None)
    if close is not None:
        try:
            await close()
        except Exception:
            return


def _model_base_url(session: Any) -> str:
    runtime = getattr(session, "runtime", None)
    model_client = getattr(runtime, "model_client", None)
    config = getattr(model_client, "config", None)
    return str(getattr(config, "base_url", "") or "")


def _model_endpoint(session: Any) -> str:
    base_url = _model_base_url(session)
    if not base_url:
        return ""
    from urllib.parse import urlparse

    parsed = urlparse(base_url)
    return parsed.netloc or base_url


def _short_path(path: str) -> str:
    try:
        value = Path(path).expanduser()
        home = Path.home()
        return "~/%s" % value.relative_to(home) if value.is_relative_to(home) else str(value)
    except Exception:
        return str(path)


def _run_id() -> str:
    return "tui_%s" % uuid4().hex


def _is_persisted_runtime_event(event: RuntimeEvent) -> bool:
    return event.type in {
        "model_message",
        "tool_approval_required",
        "tool_approval_decision",
        "tool_start",
        "tool_result",
        "error",
    }


def _new_events(events: list[RuntimeEvent], offset: int) -> list[RuntimeEvent]:
    if offset and len(events) >= offset:
        new_events = list(events)[offset:]
        return new_events or list(events)
    return list(events)


def _write(payload: dict[str, Any]) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n")
    sys.stdout.flush()


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-profile", default="")
    parser.add_argument("--system", default="")
    parser.add_argument("--profile", default="coding")
    parser.add_argument("--tools", default="")
    parser.add_argument("--permission", default="guarded")
    parser.add_argument("--workspace-path", default="")
    parser.add_argument("--sandbox-provider", default="")
    parser.add_argument("--tenant-id", default="")
    parser.add_argument("--user-id", default="")
    parser.add_argument("--agent-id", default="")
    parser.add_argument("--workspace-id", default="")
    return parser.parse_args(argv)


if __name__ == "__main__":
    main()
