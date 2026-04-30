import React from 'react'
import {Box, Text} from 'ink'
import {colors} from '../../ui/theme.js'
import {formatDuration, toolSummary} from '../../ui/format.js'
import {MessageResponse} from '../MessageResponse.js'
import {ToolUseLoader} from '../ToolUseLoader.js'
import {ToolPreview} from '../tools/ToolPreview.js'
import {ToolResultPreview} from '../tools/ToolResultPreview.js'
import type {TranscriptItem} from './types.js'

export function ToolMessage({
  item,
  collapsed,
  selected,
  expanded,
  canToggle
}: {
  item: Extract<TranscriptItem, {kind: 'tool'}>
  collapsed: boolean
  selected: boolean
  expanded?: boolean
  canToggle?: boolean
}) {
  return (
    <Box flexDirection="column" marginTop={1}>
      <Box>
        <ToolUseLoader unresolved={!item.result} error={item.error} />
        {selected ? <Text color={colors.cyan}>▸ </Text> : <Text dimColor>  </Text>}
        <Text color={selected ? colors.cyan : undefined} bold>{toolSummary(item.name, item.args)}</Text>
        <Text dimColor>  {item.name}</Text>
        {item.durationMs ? <Text dimColor>  {formatDuration(item.durationMs)}</Text> : null}
        {canToggle ? <Text dimColor>  ctrl+d</Text> : null}
      </Box>
      {item.result ? (
        <Box paddingLeft={4}>
          <Text color={item.error ? colors.error : colors.dim}>↳ {item.result}</Text>
        </Box>
      ) : null}
      {expanded ? (
        <MessageResponse>
          <Box flexDirection="column">
            <Text color={colors.dim}>details</Text>
            <ToolPreview name={item.name} args={item.args} collapsed={collapsed} showRaw />
            {item.detail ? (
              <>
                <Text color={colors.dim}>result</Text>
                <ToolResultPreview name={item.name} detail={item.detail} collapsed={collapsed} />
              </>
            ) : null}
          </Box>
        </MessageResponse>
      ) : null}
      {!expanded && selected && canToggle ? (
        <Box paddingLeft={4}>
          <Text dimColor>ctrl+d to expand arguments and raw result</Text>
        </Box>
      ) : null}
    </Box>
  )
}
