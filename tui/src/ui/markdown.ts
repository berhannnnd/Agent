export type MarkdownInline =
  | {kind: 'text'; text: string}
  | {kind: 'code'; text: string}
  | {kind: 'strong'; text: string}

export type MarkdownLine =
  | {kind: 'blank'}
  | {kind: 'heading'; level: number; parts: MarkdownInline[]}
  | {kind: 'paragraph'; parts: MarkdownInline[]}
  | {kind: 'bullet'; depth: number; marker: string; parts: MarkdownInline[]}
  | {kind: 'quote'; parts: MarkdownInline[]}
  | {kind: 'rule'}
  | {kind: 'code'; text: string}
  | {kind: 'table'; rows: string[][]}

export function parseMarkdown(text: string): MarkdownLine[] {
  const lines = text.replace(/\r\n/g, '\n').split('\n')
  const out: MarkdownLine[] = []
  let inFence = false

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index] ?? ''
    if (line.trim().startsWith('```')) {
      inFence = !inFence
      continue
    }
    if (inFence) {
      out.push({kind: 'code', text: line})
      continue
    }
    const table = readTable(lines, index)
    if (table) {
      out.push({kind: 'table', rows: table.rows})
      index = table.nextIndex - 1
      continue
    }
    out.push(parseLine(line))
  }
  return out
}

export function flattenMarkdown(lines: MarkdownLine[]): string[] {
  return lines.flatMap(line => {
    if (line.kind === 'blank') return ['']
    if (line.kind === 'rule') return ['─'.repeat(48)]
    if (line.kind === 'code') return [line.text]
    if (line.kind === 'table') return tableToLines(line.rows)
    const text = inlineText(line.parts)
    if (line.kind === 'heading') return [text]
    if (line.kind === 'quote') return [`> ${text}`]
    if (line.kind === 'bullet') return [`${'  '.repeat(line.depth)}${line.marker} ${text}`]
    return [text]
  })
}

function parseLine(line: string): MarkdownLine {
  const trimmed = line.trim()
  if (!trimmed) return {kind: 'blank'}
  if (/^(-{3,}|\*{3,}|_{3,})$/.test(trimmed)) return {kind: 'rule'}

  const heading = /^(#{1,6})\s+(.+)$/.exec(line)
  if (heading) return {kind: 'heading', level: heading[1]?.length ?? 1, parts: parseInline(heading[2] ?? '')}

  const quote = /^>\s?(.*)$/.exec(line)
  if (quote) return {kind: 'quote', parts: parseInline(quote[1] ?? '')}

  const bullet = /^(\s*)([-*+]|\d+[.)])\s+(.+)$/.exec(line)
  if (bullet) {
    return {
      kind: 'bullet',
      depth: Math.floor((bullet[1]?.length ?? 0) / 2),
      marker: bullet[2] ?? '-',
      parts: parseInline(bullet[3] ?? '')
    }
  }

  return {kind: 'paragraph', parts: parseInline(line)}
}

function parseInline(text: string): MarkdownInline[] {
  const parts: MarkdownInline[] = []
  const re = /(`[^`]+`|\*\*[^*]+\*\*)/g
  let cursor = 0
  let match: RegExpExecArray | null
  while ((match = re.exec(text))) {
    if (match.index > cursor) parts.push({kind: 'text', text: text.slice(cursor, match.index)})
    const token = match[0]
    if (token.startsWith('`')) parts.push({kind: 'code', text: token.slice(1, -1)})
    else parts.push({kind: 'strong', text: token.slice(2, -2)})
    cursor = match.index + token.length
  }
  if (cursor < text.length) parts.push({kind: 'text', text: text.slice(cursor)})
  return parts
}

function readTable(lines: string[], index: number): {rows: string[][]; nextIndex: number} | undefined {
  const header = lines[index]
  const separator = lines[index + 1]
  if (!header || !separator || !isTableRow(header) || !isSeparatorRow(separator)) return undefined
  const rows = [splitTableRow(header)]
  let nextIndex = index + 2
  while (nextIndex < lines.length && isTableRow(lines[nextIndex] ?? '')) {
    rows.push(splitTableRow(lines[nextIndex] ?? ''))
    nextIndex += 1
  }
  return {rows, nextIndex}
}

function isTableRow(line: string): boolean {
  return line.trim().startsWith('|') && line.trim().endsWith('|') && line.includes('|')
}

function isSeparatorRow(line: string): boolean {
  return /^\s*\|?[\s:-]+\|[\s|:-]*$/.test(line) && line.includes('-')
}

function splitTableRow(line: string): string[] {
  return line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map(cell => cell.trim())
}

function tableToLines(rows: string[][]): string[] {
  const widths = columnWidths(rows)
  return rows.map((row, rowIndex) => {
    const cells = widths.map((width, index) => (row[index] ?? '').padEnd(width))
    const text = ` ${cells.join('  ')} `
    return rowIndex === 0 ? text : text
  })
}

function columnWidths(rows: string[][]): number[] {
  const count = Math.max(0, ...rows.map(row => row.length))
  return Array.from({length: count}, (_, index) => Math.max(3, ...rows.map(row => (row[index] ?? '').length)))
}

function inlineText(parts: MarkdownInline[]): string {
  return parts.map(part => part.text).join('')
}
