import React from 'react'
import {Box} from 'ink'
import {useTextBuffer} from '../hooks/useTextBuffer.js'
import {PromptFooter} from './prompt/PromptFooter.js'
import {PromptLine} from './prompt/PromptLine.js'

export function PromptInput({
  disabled,
  disabledReason,
  repoRoot,
  history,
  onSubmit,
  onExit
}: {
  disabled?: boolean
  disabledReason?: string
  repoRoot: string
  history?: string[]
  onSubmit: (value: string) => void
  onExit: () => void
}) {
  const buffer = useTextBuffer({disabled, repoRoot, history, onSubmit, onExit})
  const placeholder = disabled ? disabledReason || 'waiting…' : 'ask or type / for commands'

  return (
    <Box flexDirection="column" marginTop={1}>
      <PromptLine
        disabled={disabled}
        value={buffer.value}
        before={buffer.before}
        current={buffer.current}
        after={buffer.after}
        placeholder={placeholder}
        argumentHint={buffer.activeCommand?.argumentHint && buffer.value === buffer.activeCommand.name ? buffer.activeCommand.argumentHint : undefined}
      />
      <PromptFooter suggestions={buffer.suggestions} selected={buffer.selected} historySearch={buffer.historySearch} disabled={disabled} disabledReason={disabledReason} />
    </Box>
  )
}
