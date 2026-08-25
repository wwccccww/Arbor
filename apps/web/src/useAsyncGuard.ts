import { useCallback, useRef } from 'react'

/** Ignore stale async results when inputs change mid-flight. */
export function useAsyncGuard() {
  const generation = useRef(0)

  const begin = useCallback(() => {
    generation.current += 1
    return generation.current
  }, [])

  const isLatest = useCallback((token: number) => generation.current === token, [])

  return { begin, isLatest }
}
