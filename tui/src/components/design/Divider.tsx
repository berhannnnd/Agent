import React from 'react'
import {Text} from 'ink'
import {colors} from '../../ui/theme.js'

export function Divider({
  title,
  width = 72,
  char = '─',
  color = colors.dim
}: {
  title?: string
  width?: number
  char?: string
  color?: string
}) {
  if (!title) return <Text color={color}>{char.repeat(width)}</Text>
  const label = ` ${title} `
  const side = Math.max(0, width - label.length)
  const left = Math.floor(side / 2)
  const right = side - left
  return (
    <Text color={color}>
      {char.repeat(left)}
      {label}
      {char.repeat(right)}
    </Text>
  )
}
