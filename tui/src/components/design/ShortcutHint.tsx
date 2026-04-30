import React from 'react'
import {Text} from 'ink'
import {colors, glyphs} from '../../ui/theme.js'

export function ShortcutHint({items}: {items: Array<[string, string] | string>}) {
  return (
    <Text dimColor>
      {items.map((item, index) => (
        <React.Fragment key={String(item)}>
          {index > 0 ? <Text color={colors.dim}> {glyphs.separator} </Text> : null}
          {Array.isArray(item) ? (
            <>
              <Text color={colors.text}>{item[0]}</Text>
              <Text color={colors.dim}> {item[1]}</Text>
            </>
          ) : (
            <Text color={colors.dim}>{item}</Text>
          )}
        </React.Fragment>
      ))}
    </Text>
  )
}
