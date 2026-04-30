import React, {useMemo} from 'react'
import {Text} from 'ink'
import type {ModelProfile} from '../protocol/types.js'
import {colors} from '../ui/theme.js'
import {Dialog} from './design/Dialog.js'
import {Select, type SelectOption} from './design/Select.js'
import {ShortcutHint} from './design/ShortcutHint.js'

export function ModelPicker({
  profiles,
  onSelect,
  onCancel
}: {
  profiles: ModelProfile[]
  onSelect: (name: string) => void
  onCancel: () => void
}) {
  const visibleProfiles = useMemo(() => profiles.filter(profile => profile.configured !== false), [profiles])
  const rows = visibleProfiles.length ? visibleProfiles : profiles
  const active = rows.find(profile => profile.active)
  const options: Array<SelectOption<string>> = rows.map(profile => ({
    value: profile.name,
    label: profile.name.padEnd(18),
    meta: `${profile.protocol} · ${profile.model}`,
    description: profile.endpoint || 'local/default endpoint',
    disabled: profile.configured === false,
    active: profile.active
  }))

  return (
    <Dialog
      title="Model Profiles"
      subtitle={active ? `${active.protocol} · ${active.model}` : undefined}
      borderColor={colors.border}
      footer={<ShortcutHint items={[['↑/↓', 'move'], ['enter', 'select'], ['esc', 'cancel']]} />}
    >
      {options.length ? <Select options={options} initialValue={active?.name} onSelect={onSelect} onCancel={onCancel} filterable /> : <Text dimColor>No configured model profiles</Text>}
    </Dialog>
  )
}
