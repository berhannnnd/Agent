export type RuntimeInfo = {
  protocol: string
  model: string
  model_profile?: string
  endpoint?: string
}

export type WorkspaceInfo = {
  path: string
  display: string
  tenant_id?: string
  user_id?: string
  agent_id?: string
  workspace_id?: string
}

export type RuntimeEvent = {
  type: string
  name?: string
  payload?: Record<string, unknown>
}

export type ApprovalDecision = 'allow_once' | 'allow_for_run' | 'deny'

export type PendingApproval = {
  runId: string
  approvalId: string
  toolName: string
  args: Record<string, unknown>
  risk?: string
  reason?: string
}

export type ModelProfile = {
  name: string
  protocol: string
  model: string
  endpoint?: string
  configured?: boolean
  active?: boolean
}

export type BridgeEvent =
  | {
      type: 'ready'
      runtime: RuntimeInfo
      workspace: WorkspaceInfo
      profile: string
      permission: string
      sandbox: string
      tools: string[]
      commands: string[]
    }
  | { type: 'turn_started'; run_id: string }
  | { type: 'runtime_event'; event: RuntimeEvent }
  | { type: 'turn_finished'; status: string; run_id?: string }
  | { type: 'model_profiles'; profiles: ModelProfile[] }
  | { type: 'model_switched'; profile: string; runtime: RuntimeInfo }
  | { type: 'commands'; commands: Array<{ name: string; action: string; aliases?: string[] }> }
  | { type: 'status'; status: Record<string, string> }
  | { type: 'doctor'; doctor: Record<string, string> }
  | { type: 'context'; context: Record<string, string> }
  | { type: 'trace'; trace: Array<[string, string]> }
  | { type: 'workspace'; workspace: WorkspaceInfo }
  | { type: 'tools'; tools: string[] }
  | { type: 'notice'; message: string }
  | { type: 'error'; message: string }
  | { type: 'exit' }

export type BridgeCommand =
  | { type: 'user_message'; text: string; run_id?: string }
  | { type: 'approval'; run_id: string; approvals: Record<string, boolean>; approval_scopes: Record<string, ApprovalDecision> }
  | { type: 'slash'; text: string }
  | { type: 'exit' }
