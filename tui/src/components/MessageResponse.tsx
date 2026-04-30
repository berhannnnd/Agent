import React, {createContext, useContext} from 'react'
import {Box, Text} from 'ink'
import {colors, glyphs} from '../ui/theme.js'

const MessageResponseContext = createContext(false)

export function MessageResponse({children}: {children: React.ReactNode}) {
  const nested = useContext(MessageResponseContext)
  if (nested) return <>{children}</>

  return (
    <MessageResponseContext.Provider value={true}>
      <Box flexDirection="row" flexShrink={1}>
        <Box flexShrink={0} minWidth={4}>
          <Text color={colors.dim}>  {glyphs.response} </Text>
        </Box>
        <Box flexDirection="column" flexGrow={1} flexShrink={1}>
          {children}
        </Box>
      </Box>
    </MessageResponseContext.Provider>
  )
}
