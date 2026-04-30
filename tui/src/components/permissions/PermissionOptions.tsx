import React from 'react'
import type {ApprovalDecision} from '../../protocol/types.js'
import {Select, type SelectOption} from '../design/Select.js'

const OPTIONS: Array<SelectOption<ApprovalDecision>> = [
  {value: 'allow_once', label: 'Allow once', shortcut: 'y', description: 'Approve this tool call only.'},
  {value: 'allow_for_run', label: 'Allow for run', shortcut: 'r', description: 'Approve matching calls while this run continues.'},
  {value: 'deny', label: 'Deny', shortcut: 'n', description: 'Reject this tool call and return control to the agent.'}
]

export function PermissionOptions({onDecision}: {onDecision: (decision: ApprovalDecision) => void}) {
  return <Select options={OPTIONS} onSelect={onDecision} onCancel={() => onDecision('deny')} />
}
