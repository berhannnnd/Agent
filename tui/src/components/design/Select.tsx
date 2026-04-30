import React, {useMemo, useState} from 'react'
import {Box, Text, useInput, useStdin} from 'ink'
import figures from 'figures'
import {colors} from '../../ui/theme.js'
import {dropLastChar} from '../../ui/textBuffer.js'

export type SelectOption<T extends string = string> = {
  value: T
  label: string
  description?: string
  meta?: string
  shortcut?: string
  disabled?: boolean
  active?: boolean
}

export function Select<T extends string>({
  options,
  initialValue,
  onSelect,
  onCancel,
  active = true,
  filterable = false
}: {
  options: Array<SelectOption<T>>
  initialValue?: T
  onSelect: (value: T) => void
  onCancel?: () => void
  active?: boolean
  filterable?: boolean
}) {
  const [query, setQuery] = useState('')
  const filteredOptions = useMemo(() => {
    if (!filterable || !query.trim()) return options
    const needle = query.trim().toLowerCase()
    return options.filter(option => [option.label, option.meta, option.description].filter(Boolean).join(' ').toLowerCase().includes(needle))
  }, [filterable, options, query])
  const enabledOptions = useMemo(() => filteredOptions.filter(option => !option.disabled), [filteredOptions])
  const initialIndex = Math.max(0, enabledOptions.findIndex(option => option.value === initialValue || option.active))
  const [selected, setSelected] = useState(initialIndex)
  const {isRawModeSupported} = useStdin()
  const selectedOption = enabledOptions[Math.min(selected, Math.max(0, enabledOptions.length - 1))]

  useInput((input, key) => {
    const shortcut = enabledOptions.find(option => option.shortcut === input)
    if (shortcut) {
      onSelect(shortcut.value)
      return
    }
    if (filterable && key.backspace) {
      setQuery(dropLastChar)
      setSelected(0)
      return
    }
    if (filterable && input && !key.ctrl && !key.meta && !key.return) {
      setQuery(current => current + input)
      setSelected(0)
      return
    }
    if (!enabledOptions.length) {
      if (key.escape || (key.ctrl && input === 'c')) onCancel?.()
      return
    }
    if (key.escape || (key.ctrl && input === 'c')) {
      if (filterable && query) {
        setQuery('')
        setSelected(0)
        return
      }
      onCancel?.()
      return
    }
    if (key.upArrow) {
      setSelected(current => (current - 1 + enabledOptions.length) % enabledOptions.length)
      return
    }
    if (key.downArrow) {
      setSelected(current => (current + 1) % enabledOptions.length)
      return
    }
    if (key.return && selectedOption) onSelect(selectedOption.value)
  }, {isActive: Boolean(active && isRawModeSupported)})

  if (!options.length) return <Text dimColor>No options available</Text>

  return (
    <Box flexDirection="column">
      {filterable ? (
        <Box marginBottom={1}>
          <Text dimColor>filter: </Text>
          <Text>{query || ' '}</Text>
        </Box>
      ) : null}
      {filteredOptions.map(option => {
        const index = enabledOptions.findIndex(enabled => enabled.value === option.value)
        const selectedRow = index === selected && !option.disabled
        return (
          <Box key={option.value} flexDirection="column">
            <Box>
              <Text color={selectedRow ? colors.cyan : option.disabled ? colors.dim : colors.text}>
                {selectedRow ? figures.pointer : ' '} {option.active ? '●' : ' '} {option.label}
              </Text>
              {option.shortcut ? <Text dimColor>  {option.shortcut}</Text> : null}
              {option.meta ? <Text dimColor>  {option.meta}</Text> : null}
            </Box>
            {option.description ? (
              <Box paddingLeft={4}>
                <Text dimColor>{option.description}</Text>
              </Box>
            ) : null}
          </Box>
        )
      })}
      {!filteredOptions.length ? <Text dimColor>No matching options</Text> : null}
    </Box>
  )
}
