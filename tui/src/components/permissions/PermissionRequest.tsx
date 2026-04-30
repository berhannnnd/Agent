import React from 'react'
import {Box} from 'ink'
import type {ApprovalDecision, PendingApproval} from '../../protocol/types.js'
import {colors} from '../../ui/theme.js'
import {Dialog} from '../design/Dialog.js'
import {ShortcutHint} from '../design/ShortcutHint.js'
import {PermissionOptions} from './PermissionOptions.js'
import {PermissionRequestBody} from './PermissionRequestBody.js'

export function PermissionRequest({
  approval,
  onDecision
}: {
  approval: PendingApproval
  onDecision: (decision: ApprovalDecision) => void
}) {
  return (
    <Dialog
      title="Permission Request"
      subtitle={approval.toolName}
      borderColor={colors.warning}
      footer={<ShortcutHint items={[['y', 'allow once'], ['r', 'allow run'], ['n/esc', 'deny']]} />}
    >
      <Box flexDirection="column">
        <PermissionRequestBody approval={approval} />
        <Box marginTop={1}>
          <PermissionOptions onDecision={onDecision} />
        </Box>
      </Box>
    </Dialog>
  )
}
