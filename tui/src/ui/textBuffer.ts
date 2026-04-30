export function charLength(value: string): number {
  return Array.from(value).length
}

export function sliceChars(value: string, start: number, end?: number): string {
  return Array.from(value).slice(start, end).join('')
}

export function charAt(value: string, index: number): string | undefined {
  return Array.from(value)[index]
}

export function insertAt(value: string, cursor: number, text: string): string {
  const chars = Array.from(value)
  chars.splice(cursor, 0, text)
  return chars.join('')
}

export function removeBefore(value: string, cursor: number): string {
  const chars = Array.from(value)
  chars.splice(Math.max(0, cursor - 1), 1)
  return chars.join('')
}

export function removeAt(value: string, cursor: number): string {
  const chars = Array.from(value)
  chars.splice(cursor, 1)
  return chars.join('')
}

export function dropLastChar(value: string): string {
  return Array.from(value).slice(0, -1).join('')
}
