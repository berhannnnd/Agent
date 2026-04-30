import React from 'react'
import {Box, Text} from 'ink'
import {looksLikeDiff} from '../../ui/diff.js'
import {colors} from '../../ui/theme.js'
import {toolPresentation} from '../../ui/toolPresentation.js'
import {CollapsibleBlock} from '../CollapsibleBlock.js'
import {DiffPreview} from './DiffPreview.js'

export function ToolPreview({
  name,
  args,
  collapsed = true,
  showRaw = false
}: {
  name: string
  args?: Record<string, unknown>
  collapsed?: boolean
  showRaw?: boolean
}) {
  const presentation = toolPresentation(name, args)
  const hasRaw = Boolean(args && Object.keys(args).length)

  return (
    <Box flexDirection="column">
      <Text>
        <Text color={colors.cyan}>action    </Text>
        <Text>{presentation.action}</Text>
      </Text>
      {presentation.target ? (
        <Text>
          <Text color={colors.cyan}>target    </Text>
          <Text>{presentation.target}</Text>
        </Text>
      ) : null}
      {presentation.meta ? (
        <Text>
          <Text color={colors.cyan}>meta      </Text>
          <Text dimColor>{presentation.meta}</Text>
        </Text>
      ) : null}
      {presentation.preview ? (
        <Box flexDirection="column" marginTop={1}>
          <Text color={colors.dim}>{presentation.previewLabel || 'preview'}</Text>
          {looksLikeDiff(presentation.preview) ? (
            <DiffPreview diff={presentation.preview} collapsed={collapsed} maxLines={10} />
          ) : (
            <CollapsibleBlock text={presentation.preview} collapsed={collapsed} maxLines={8} />
          )}
        </Box>
      ) : null}
      {showRaw && hasRaw ? (
        <Box flexDirection="column" marginTop={1}>
          <Text color={colors.dim}>arguments</Text>
          <CollapsibleBlock text={JSON.stringify(args, null, 2)} collapsed={collapsed} maxLines={8} />
        </Box>
      ) : null}
    </Box>
  )
}
