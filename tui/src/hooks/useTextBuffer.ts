import {useEffect, useMemo, useState} from 'react'
import {useInput, useStdin} from 'ink'
import {commandMatches, findCommand} from '../ui/commands.js'
import {charAt, charLength, insertAt, removeAt, removeBefore, sliceChars} from '../ui/textBuffer.js'
import {useFileSuggestions} from './useFileSuggestions.js'

export function useTextBuffer({
  disabled,
  repoRoot,
  history,
  onSubmit,
  onExit
}: {
  disabled?: boolean
  repoRoot: string
  history?: string[]
  onSubmit: (value: string) => void
  onExit: () => void
}) {
  const [value, setValue] = useState('')
  const [cursor, setCursor] = useState(0)
  const [selected, setSelected] = useState(0)
  const [historyIndex, setHistoryIndex] = useState<number | null>(null)
  const [historyDraft, setHistoryDraft] = useState('')
  const [historySearchActive, setHistorySearchActive] = useState(false)
  const [historyQuery, setHistoryQuery] = useState('')
  const [historyMatchIndex, setHistoryMatchIndex] = useState(0)
  const {isRawModeSupported} = useStdin()
  const fileSuggestions = useFileSuggestions({repoRoot, value, cursor})
  const commandSuggestions = useMemo(() => commandMatches(value), [value])
  const suggestions = useMemo(() => {
    if (historySearchActive) return []
    if (fileSuggestions.active) return fileSuggestions.suggestions
    return commandSuggestions
  }, [commandSuggestions, fileSuggestions.active, fileSuggestions.suggestions, historySearchActive])
  const activeCommand = fileSuggestions.active ? undefined : findCommand(value)
  const historyMatches = useMemo(() => {
    if (!history?.length) return []
    const query = historyQuery.trim().toLowerCase()
    const source = [...history].reverse()
    return query ? source.filter(item => item.toLowerCase().includes(query)) : source
  }, [history, historyQuery])
  const historyMatch = historyMatches[Math.min(historyMatchIndex, Math.max(0, historyMatches.length - 1))]

  useEffect(() => {
    setSelected(current => Math.min(current, Math.max(0, suggestions.length - 1)))
  }, [suggestions.length])

  useInput((input, key) => {
    if (disabled) return
    if (key.ctrl && input === 'c') {
      onExit()
      return
    }
    if (historySearchActive) {
      handleHistorySearchInput(input, key)
      return
    }
    if (key.ctrl && input === 'r') {
      setHistorySearchActive(true)
      setHistoryQuery('')
      setHistoryMatchIndex(0)
      return
    }
    if (key.return) {
      const text = value.trim()
      if (text) onSubmit(text)
      reset()
      return
    }
    if (key.escape && value) {
      reset()
      return
    }
    if (key.backspace) {
      removeBeforeCursor()
      return
    }
    if (key.delete) {
      removeAfterCursor()
      return
    }
    if (key.leftArrow && (key.ctrl || key.meta)) {
      setCursor(current => previousWordBoundary(value, current))
      return
    }
    if (key.rightArrow && (key.ctrl || key.meta)) {
      setCursor(current => nextWordBoundary(value, current))
      return
    }
    if (key.leftArrow) {
      setCursor(current => Math.max(0, current - 1))
      return
    }
    if (key.rightArrow) {
      setCursor(current => Math.min(charLength(value), current + 1))
      return
    }
    if (key.ctrl && input === 'a') {
      setCursor(0)
      return
    }
    if (key.ctrl && input === 'e') {
      setCursor(charLength(value))
      return
    }
    if (key.ctrl && input === 'w') {
      removeWordBeforeCursor()
      return
    }
    if (key.ctrl && input === 'u') {
      setValue(current => sliceChars(current, cursor))
      setCursor(0)
      setHistoryIndex(null)
      setSelected(0)
      return
    }
    if (key.ctrl && input === 'k') {
      setValue(current => sliceChars(current, 0, cursor))
      setHistoryIndex(null)
      setSelected(0)
      return
    }
    if (key.upArrow && suggestions.length) {
      setSelected(current => (current - 1 + suggestions.length) % suggestions.length)
      return
    }
    if (key.downArrow && suggestions.length) {
      setSelected(current => (current + 1) % suggestions.length)
      return
    }
    if (key.upArrow && history?.length) {
      showHistory(-1)
      return
    }
    if (key.downArrow && history?.length && historyIndex !== null) {
      showHistory(1)
      return
    }
    if (key.tab && suggestions.length) {
      const suggestion = suggestions[selected]
      const next = suggestion?.insertText ?? suggestion?.name ?? value
      if (fileSuggestions.active && suggestion?.kind === 'file') replaceRange(fileSuggestions.start, cursor, next)
      else replace(next)
      return
    }
    if (input && !key.meta && !key.ctrl) {
      insert(input)
    }
  }, {isActive: Boolean(!disabled && isRawModeSupported)})

  function insert(text: string) {
    setValue(current => insertAt(current, cursor, text))
    setCursor(current => current + charLength(text))
    setHistoryIndex(null)
    setSelected(0)
  }

  function replace(text: string) {
    setValue(text)
    setCursor(charLength(text))
    setSelected(0)
    setHistoryIndex(null)
  }

  function replaceRange(start: number, end: number, text: string) {
    const next = `${sliceChars(value, 0, start)}${text}${sliceChars(value, end)}`
    setValue(next)
    setCursor(start + charLength(text))
    setSelected(0)
    setHistoryIndex(null)
  }

  function removeBeforeCursor() {
    if (cursor <= 0) return
    setValue(current => removeBefore(current, cursor))
    setCursor(current => Math.max(0, current - 1))
    setHistoryIndex(null)
    setSelected(0)
  }

  function removeAfterCursor() {
    if (cursor >= charLength(value)) return
    setValue(current => removeAt(current, cursor))
    setHistoryIndex(null)
    setSelected(0)
  }

  function removeWordBeforeCursor() {
    if (cursor <= 0) return
    const chars = Array.from(value)
    let start = cursor
    while (start > 0 && /\s/.test(chars[start - 1] ?? '')) start -= 1
    while (start > 0 && !/\s/.test(chars[start - 1] ?? '')) start -= 1
    chars.splice(start, cursor - start)
    setValue(chars.join(''))
    setCursor(start)
    setHistoryIndex(null)
    setSelected(0)
  }

  function handleHistorySearchInput(input: string, key: {
    return?: boolean
    escape?: boolean
    backspace?: boolean
    delete?: boolean
    upArrow?: boolean
    downArrow?: boolean
    ctrl?: boolean
    meta?: boolean
  }) {
    if (key.escape || (key.ctrl && input === 'g')) {
      closeHistorySearch()
      return
    }
    if (key.return) {
      if (historyMatch) replace(historyMatch)
      closeHistorySearch()
      return
    }
    if (key.upArrow && historyMatches.length) {
      setHistoryMatchIndex(current => (current - 1 + historyMatches.length) % historyMatches.length)
      return
    }
    if (key.downArrow && historyMatches.length) {
      setHistoryMatchIndex(current => (current + 1) % historyMatches.length)
      return
    }
    if (key.backspace || key.delete) {
      setHistoryQuery(current => removeBefore(current, charLength(current)))
      setHistoryMatchIndex(0)
      return
    }
    if (input && !key.meta && !key.ctrl) {
      setHistoryQuery(current => current + input)
      setHistoryMatchIndex(0)
    }
  }

  function closeHistorySearch() {
    setHistorySearchActive(false)
    setHistoryQuery('')
    setHistoryMatchIndex(0)
  }

  function showHistory(direction: -1 | 1) {
    if (!history?.length) return
    if (direction < 0) {
      const nextIndex = historyIndex === null ? history.length - 1 : Math.max(0, historyIndex - 1)
      if (historyIndex === null) setHistoryDraft(value)
      const next = history[nextIndex] ?? ''
      setHistoryIndex(nextIndex)
      setValue(next)
      setCursor(charLength(next))
      return
    }
    if (historyIndex === null) return
    const nextIndex = historyIndex + 1
    if (nextIndex >= history.length) {
      setHistoryIndex(null)
      setValue(historyDraft)
      setCursor(charLength(historyDraft))
    } else {
      const next = history[nextIndex] ?? ''
      setHistoryIndex(nextIndex)
      setValue(next)
      setCursor(charLength(next))
    }
  }

  function reset() {
    setValue('')
    setCursor(0)
    setSelected(0)
    setHistoryIndex(null)
    setHistoryDraft('')
    closeHistorySearch()
  }

  return {
    value,
    cursor,
    selected,
    suggestions,
    activeCommand,
    historySearch: {
      active: historySearchActive,
      query: historyQuery,
      match: historyMatch,
      failed: Boolean(historyQuery && !historyMatches.length)
    },
    before: sliceChars(value, 0, cursor),
    current: charAt(value, cursor) ?? ' ',
    after: sliceChars(value, cursor + 1)
  }
}

function previousWordBoundary(value: string, cursor: number): number {
  const chars = Array.from(value)
  let index = Math.min(cursor, chars.length)
  while (index > 0 && /\s/.test(chars[index - 1] ?? '')) index -= 1
  while (index > 0 && !/\s/.test(chars[index - 1] ?? '')) index -= 1
  return index
}

function nextWordBoundary(value: string, cursor: number): number {
  const chars = Array.from(value)
  let index = Math.min(cursor, chars.length)
  while (index < chars.length && /\s/.test(chars[index] ?? '')) index += 1
  while (index < chars.length && !/\s/.test(chars[index] ?? '')) index += 1
  return index
}
