import React from 'react'
import {Box, Text} from 'ink'
import {Panel} from './design/Panel.js'
import {colors} from '../ui/theme.js'
import type {RuntimeInfo, WorkspaceInfo} from '../protocol/types.js'

export function Welcome({
  runtime,
  workspace,
  profile,
  permission,
  sandbox,
  toolCount
}: {
  runtime?: RuntimeInfo
  workspace?: WorkspaceInfo
  profile?: string
  permission?: string
  sandbox?: string
  toolCount?: number
}) {
  return (
    <Box flexDirection="column" marginTop={1} marginBottom={1}>
      <Text color={colors.warning}>Tip: You can launch Agents Code with just <Text bold>make cli</Text></Text>
      <Text color={colors.accent}>  Agents Code v0.1.0</Text>
      <Panel>
        <Box flexDirection="row">
          <Box width="34%" minWidth={34} flexDirection="column" alignItems="center" paddingY={1}>
            <Text bold>Welcome back!</Text>
            <Box height={1} />
            <Text color={colors.accent} bold>
              Agents Code
            </Text>
            <Text dimColor>local coding agent</Text>
            <Box height={1} />
            <Text dimColor>{runtime?.model_profile || runtime?.protocol || 'model'} · {runtime?.model || 'loading'}</Text>
            <Text dimColor>{workspace?.display || 'workspace'}</Text>
          </Box>
          <Box borderStyle="single" borderColor={colors.border} borderTop={false} borderRight={false} borderBottom={false} paddingLeft={1} flexDirection="column" flexGrow={1}>
            <Text color={colors.accent} bold>Tips for getting started</Text>
            <Text>Use <Text color={colors.cyan}>/model</Text> to switch profiles</Text>
            <Box marginY={0}>
              <Text color={colors.accent}>{'─'.repeat(32)}</Text>
            </Box>
            <Text color={colors.accent} bold>Session</Text>
            <Text dimColor>{profile || 'coding'} · {permission || 'guarded'} · {sandbox || 'local'} · {toolCount ?? 0} tools</Text>
            <Text dimColor>/help /status /doctor /tools</Text>
          </Box>
        </Box>
      </Panel>
    </Box>
  )
}
