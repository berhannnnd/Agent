import React, {type ReactNode} from 'react'
import {Box} from 'ink'
import {colors} from '../../ui/theme.js'

export function Panel({children, borderColor = colors.border}: {children: ReactNode; borderColor?: string}) {
  return (
    <Box borderStyle="round" borderColor={borderColor} paddingX={1} paddingY={0} flexDirection="column">
      {children}
    </Box>
  )
}
