import React from 'react'
import {Box, Text} from 'ink'
import type {RuntimeInfo, WorkspaceInfo} from '../protocol/types.js'
import {colors, glyphs} from '../ui/theme.js'

export function StatusLine({
  runtime,
  workspace,
  permission,
  sandbox,
  toolCount,
  busy,
  folded,
  queued = 0
}: {
  runtime?: RuntimeInfo
  workspace?: WorkspaceInfo
  permission: string
  sandbox: string
  toolCount: number
  busy: boolean
  folded: boolean
  queued?: number
}) {
  return (
    <Box flexDirection="column" borderStyle="single" borderLeft={false} borderRight={false} borderBottom={false} borderColor={colors.dim} marginTop={1}>
      <Text dimColor>
        {busy ? <Text color={colors.cyan}>● working</Text> : '● idle'}
        {' '}{glyphs.separator}{' '}
        {runtime?.model_profile || runtime?.protocol || 'model'} {runtime?.model ? `· ${runtime.model}` : ''}
        {' '}{glyphs.separator}{' '}
        {permission}
        {' '}{glyphs.separator}{' '}
        {sandbox}
        {' '}{glyphs.separator}{' '}
        {toolCount} tools
        {' '}{glyphs.separator}{' '}
        {folded ? 'folded' : 'expanded'}
        {queued ? (
          <>
            {' '}{glyphs.separator}{' '}
            {queued} queued
          </>
        ) : null}
      </Text>
      {workspace?.display ? <Text dimColor>cwd {workspace.display}</Text> : null}
    </Box>
  )
}
