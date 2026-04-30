import {useEffect, useState} from 'react'

export function useBlink(enabled: boolean, intervalMs = 480): boolean {
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    if (!enabled) {
      setVisible(true)
      return
    }
    const timer = setInterval(() => setVisible(current => !current), intervalMs)
    return () => clearInterval(timer)
  }, [enabled, intervalMs])

  return visible
}
