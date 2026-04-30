import React from 'react'
import {Box, Text} from 'ink'
import {colors, glyphs} from '../../ui/theme.js'
import {MessageResponse} from '../MessageResponse.js'
import type {TranscriptItem} from './types.js'

type ModelProfileRows = Extract<TranscriptItem, {kind: 'models'}>['profiles']

export function ModelProfilesMessage({profiles}: {profiles: ModelProfileRows}) {
  return (
    <Box flexDirection="column" marginTop={1}>
      <Text bold>Model Profiles</Text>
      <MessageResponse>
        {profiles.map(profile => (
          <Text key={profile.name}>
            <Text color={profile.active ? colors.cyan : colors.dim}>{profile.active ? glyphs.active : ' '} </Text>
            <Text bold={profile.active}>{profile.name.padEnd(17)}</Text>
            <Text color={profile.active ? colors.cyan : undefined}>{profile.protocol} · {profile.model}</Text>
            <Text dimColor>  {profile.endpoint || '-'}</Text>
            {!profile.configured ? <Text color={colors.warning}> missing</Text> : null}
          </Text>
        ))}
      </MessageResponse>
    </Box>
  )
}
