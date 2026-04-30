import React from 'react'
import {Box, Text} from 'ink'
import type {PendingApproval} from '../../protocol/types.js'
import {compact, toolSummary} from '../../ui/format.js'
import {colors} from '../../ui/theme.js'
import {ToolPreview} from '../tools/ToolPreview.js'

export function PermissionRequestBody({approval}: {approval: PendingApproval}) {
  return (
    <Box flexDirection="column">
      <Text>
        <Text color={colors.warning}>operation </Text>
        <Text>{toolSummary(approval.toolName, approval.args)}</Text>
      </Text>
      {approval.risk ? (
        <Text>
          <Text color={colors.warning}>risk      </Text>
          <Text>{approval.risk}</Text>
        </Text>
      ) : null}
      {approval.reason ? (
        <Text>
          <Text color={colors.warning}>reason    </Text>
          <Text dimColor>{compact(approval.reason, 160)}</Text>
        </Text>
      ) : null}
      <Box marginTop={1}>
        <ToolPreview name={approval.toolName} args={approval.args} collapsed showRaw />
      </Box>
    </Box>
  )
}
