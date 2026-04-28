from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent.governance.audit import ApprovalAuditStore
from agent.capabilities.memory import MemoryStore
from agent.runtime import CheckpointStore
from agent.governance import CredentialRefStore
from agent.state import AgentProfileStore, IdentityStore, RunStore, WorkspaceStore
from agent.governance.tracing import TraceStore
from gateway.sessions import (
    create_agent_profile_store,
    create_approval_audit_store,
    create_checkpoint_store,
    create_credential_ref_store,
    create_identity_store,
    create_memory_store,
    create_run_store,
    create_trace_store,
    create_workspace_store,
)


@dataclass(frozen=True)
class GatewayPersistence:
    runs: RunStore
    checkpoints: CheckpointStore
    traces: TraceStore
    approval_audit: ApprovalAuditStore
    identities: IdentityStore
    agent_profiles: AgentProfileStore
    workspaces: WorkspaceStore
    memories: MemoryStore
    credentials: CredentialRefStore


def create_gateway_persistence(settings: Any) -> GatewayPersistence:
    return GatewayPersistence(
        runs=create_run_store(settings),
        checkpoints=create_checkpoint_store(settings),
        traces=create_trace_store(settings),
        approval_audit=create_approval_audit_store(settings),
        identities=create_identity_store(settings),
        agent_profiles=create_agent_profile_store(settings),
        workspaces=create_workspace_store(settings),
        memories=create_memory_store(settings),
        credentials=create_credential_ref_store(settings),
    )
