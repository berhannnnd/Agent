import React from 'react'
import type {ApprovalDecision, PendingApproval} from '../protocol/types.js'
import {PermissionRequest} from './permissions/PermissionRequest.js'

export function ApprovalPrompt({
  approval,
  onDecision
}: {
  approval: PendingApproval
  onDecision: (decision: ApprovalDecision) => void
}) {
  return <PermissionRequest approval={approval} onDecision={onDecision} />
}
