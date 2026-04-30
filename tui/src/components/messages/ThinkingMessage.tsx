import React from 'react'
import {Box, Text} from 'ink'
import {colors} from '../../ui/theme.js'
import {MarkdownBlock} from '../MarkdownBlock.js'
import {MessageResponse} from '../MessageResponse.js'

import {LiveBadge} from '../design/LiveBadge.js'

export function ThinkingMessage({text, collapsed, live}: {text: string; collapsed: boolean; live?: boolean}) {
  return (
    <Box marginTop={1} flexDirection="column">
      <Text color={colors.cyan}>thinking{live ? <LiveBadge /> : null}</Text>
      <MessageResponse>
        <MarkdownBlock text={text} collapsed={collapsed} maxLines={5} />
      </MessageResponse>
    </Box>
  )
}
