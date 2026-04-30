import {useRef, useState} from 'react'

export function useInputQueue(onRun: (value: string) => void) {
  const [items, setItems] = useState<string[]>([])
  const itemsRef = useRef<string[]>([])
  const onRunRef = useRef(onRun)
  onRunRef.current = onRun

  function enqueue(value: string) {
    setItems(current => {
      const next = [...current, value]
      itemsRef.current = next
      return next
    })
  }

  function runNext() {
    setItems(current => {
      const [next, ...rest] = current
      itemsRef.current = rest
      if (next) queueMicrotask(() => onRunRef.current(next))
      return rest
    })
  }

  function clear(): number {
    const count = itemsRef.current.length
    itemsRef.current = []
    setItems([])
    return count
  }

  return {items, enqueue, runNext, clear}
}
