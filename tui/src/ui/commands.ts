export type CommandDef = {
  kind?: 'command' | 'file'
  name: string
  description: string
  argumentHint?: string
  local?: boolean
  availability?: 'idle' | 'always'
  insertText?: string
}

export const COMMANDS: CommandDef[] = [
  {name: '/help', description: 'show commands', local: true, availability: 'always'},
  {name: '/model', description: 'list or switch configured model profiles', argumentHint: '<profile>', availability: 'idle'},
  {name: '/status', description: 'session state'},
  {name: '/doctor', description: 'local readiness check'},
  {name: '/tools', description: 'enabled tools'},
  {name: '/workspace', description: 'workspace scope'},
  {name: '/context', description: 'context window usage'},
  {name: '/trace', description: 'context assembly trace'},
  {name: '/fold', description: 'collapse long blocks', local: true, availability: 'always'},
  {name: '/unfold', description: 'expand long blocks', local: true, availability: 'always'},
  {name: '/queue', description: 'show queued messages', local: true, availability: 'always'},
  {name: '/cancel', description: 'clear queued messages', local: true, availability: 'always'},
  {name: '/clear', description: 'clear conversation', availability: 'idle'},
  {name: '/exit', description: 'leave the chat', availability: 'always'}
]

export function commandMatches(value: string): CommandDef[] {
  if (!value.startsWith('/')) return []
  const [command] = value.split(/\s+/, 1)
  return COMMANDS.filter(item => item.name.startsWith(command || '/')).slice(0, 9)
}

export function findCommand(value: string): CommandDef | undefined {
  const [command] = value.trim().split(/\s+/, 1)
  return COMMANDS.find(item => item.name === command)
}
