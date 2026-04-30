import {spawn} from 'node:child_process'
import path from 'node:path'
import {useEffect, useMemo, useState} from 'react'
import {charLength, sliceChars} from '../ui/textBuffer.js'
import type {CommandDef} from '../ui/commands.js'

type ActiveReference = {
  start: number
  query: string
}

const ignoredPathParts = new Set(['.git', '.venv', 'node_modules', 'nexus-code', 'old', 'agents.egg-info', '.pytest_cache', 'artifacts', 'logs'])
const fileIndexCache = new Map<string, Promise<string[]>>()

export function useFileSuggestions({
  repoRoot,
  value,
  cursor
}: {
  repoRoot: string
  value: string
  cursor: number
}) {
  const reference = useMemo(() => activeReference(value, cursor), [value, cursor])
  const [paths, setPaths] = useState<string[]>([])

  useEffect(() => {
    if (!reference) return
    let cancelled = false
    loadFileIndex(repoRoot).then(result => {
      if (!cancelled) setPaths(result)
    }).catch(() => {
      if (!cancelled) setPaths([])
    })
    return () => {
      cancelled = true
    }
  }, [repoRoot, reference?.query])

  const suggestions = useMemo(() => {
    if (!reference) return []
    return matchFileSuggestions(paths, reference.query)
  }, [paths, reference])

  return {
    active: Boolean(reference),
    start: reference?.start ?? 0,
    suggestions
  }
}

function activeReference(value: string, cursor: number): ActiveReference | null {
  const before = sliceChars(value, 0, cursor)
  const match = /(^|\s)@([^\s]*)$/.exec(before)
  if (!match) return null
  const query = match[2] ?? ''
  return {
    start: charLength(before) - query.length - 1,
    query
  }
}

function matchFileSuggestions(paths: string[], query: string): CommandDef[] {
  const normalized = query.toLowerCase()
  const scored = paths
    .map(item => ({item, score: fileScore(item, normalized)}))
    .filter(item => item.score >= 0)
    .sort((a, b) => a.score - b.score || a.item.localeCompare(b.item))
    .slice(0, 8)
  return scored.map(({item}) => ({
    kind: 'file',
    name: item,
    description: path.dirname(item) === '.' ? 'file' : path.dirname(item),
    insertText: `@${item}`
  }))
}

function fileScore(item: string, query: string): number {
  if (!query) return item.includes('/') ? 2 : 1
  const target = item.toLowerCase()
  const base = path.basename(target)
  if (target === query || base === query) return 0
  if (base.startsWith(query)) return 1
  if (target.startsWith(query)) return 2
  if (base.includes(query)) return 3
  if (target.includes(query)) return 4
  return fuzzyIncludes(target, query) ? 5 : -1
}

function fuzzyIncludes(target: string, query: string): boolean {
  let index = 0
  for (const char of target) {
    if (char === query[index]) index += 1
    if (index >= query.length) return true
  }
  return false
}

async function loadFileIndex(repoRoot: string): Promise<string[]> {
  const root = path.resolve(repoRoot)
  const cached = fileIndexCache.get(root)
  if (cached) return cached
  const promise = readRgFiles(root).then(paths => paths.filter(shouldKeepPath))
  fileIndexCache.set(root, promise)
  return promise
}

function shouldKeepPath(value: string): boolean {
  return !value.split('/').some(part => ignoredPathParts.has(part))
}

function readRgFiles(cwd: string): Promise<string[]> {
  return new Promise((resolve, reject) => {
    const child = spawn('rg', ['--files', '--hidden'], {cwd, stdio: ['ignore', 'pipe', 'ignore']})
    let output = ''
    child.stdout.setEncoding('utf8')
    child.stdout.on('data', chunk => {
      output += chunk
    })
    child.on('error', reject)
    child.on('close', code => {
      if (code !== 0) {
        reject(new Error(`rg exited with ${code}`))
        return
      }
      resolve(output.split('\n').map(line => line.trim()).filter(Boolean))
    })
  })
}
