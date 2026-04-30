import {useEffect, useState} from 'react'

export function useTicker(active = true, intervalMs = 120): number {
  const [tick, setTick] = useState(0)

  useEffect(() => {
    if (!active) return undefined
    const timer = setInterval(() => setTick(current => current + 1), intervalMs)
    return () => clearInterval(timer)
  }, [active, intervalMs])

  return tick
}
