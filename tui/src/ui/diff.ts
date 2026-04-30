export type DiffLineKind = 'file' | 'hunk' | 'add' | 'remove' | 'context' | 'meta'

export type DiffLine = {
  kind: DiffLineKind
  text: string
}

export type DiffStats = {
  files: number
  added: number
  removed: number
}

export function looksLikeDiff(value: string): boolean {
  return /^(diff --git|@@ |--- |\+\+\+ )/m.test(value)
}

export function parseUnifiedDiff(value: string): DiffLine[] {
  return value.split('\n').map(text => {
    if (text.startsWith('diff --git') || text.startsWith('--- ') || text.startsWith('+++ ')) {
      return {kind: 'file', text}
    }
    if (text.startsWith('@@')) return {kind: 'hunk', text}
    if (text.startsWith('+')) return {kind: 'add', text}
    if (text.startsWith('-')) return {kind: 'remove', text}
    if (text.startsWith(' ')) return {kind: 'context', text}
    return {kind: 'meta', text}
  })
}

export function diffStats(value: string): DiffStats {
  const files = new Set<string>()
  let added = 0
  let removed = 0
  for (const line of value.split('\n')) {
    if (line.startsWith('+++ ')) {
      files.add(normalizeDiffPath(line.slice(4)))
      continue
    }
    if (line.startsWith('--- ') || line.startsWith('diff --git')) continue
    if (line.startsWith('+')) added += 1
    else if (line.startsWith('-')) removed += 1
  }
  return {files: files.size, added, removed}
}

function normalizeDiffPath(value: string): string {
  if (value === '/dev/null') return value
  return value.replace(/^"[ab]\//, '"').replace(/^[ab]\//, '')
}
