import {useEffect, useRef, useState} from 'react'

export function useLiveDraft({
  delayMs = 32,
  trimLive = false
}: {
  delayMs?: number
  trimLive?: boolean
} = {}) {
  const draft = useRef('')
  const timer = useRef<NodeJS.Timeout | null>(null)
  const [live, setLive] = useState('')

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current)
  }, [])

  function append(delta: string) {
    draft.current += delta
    schedule()
  }

  function value() {
    return draft.current
  }

  function flush({trim = false}: {trim?: boolean} = {}) {
    const text = trim ? draft.current.trim() : draft.current
    clear()
    return text
  }

  function clear() {
    if (timer.current) {
      clearTimeout(timer.current)
      timer.current = null
    }
    draft.current = ''
    setLive('')
  }

  function schedule() {
    if (timer.current) return
    timer.current = setTimeout(() => {
      timer.current = null
      setLive(trimLive ? draft.current.trim() : draft.current)
    }, delayMs)
  }

  return {live, append, value, flush, clear}
}
